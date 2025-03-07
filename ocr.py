import os
import sys
import json
import base64
import re
from pathlib import Path
import markdown
from mistralai import Mistral
from mistralai import DocumentURLChunk, ImageURLChunk, TextChunk
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTextEdit, QComboBox, 
                             QGroupBox, QLineEdit, QProgressBar, QMessageBox,
                             QStatusBar, QTabWidget, QSplitter)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap, QFont
import fitz  # PyMuPDF库用于提取PDF图片
import uuid
import shutil

class PdfImageExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        
    def extract_images(self, output_folder):
        """从PDF提取所有图片并保存到指定文件夹"""
        os.makedirs(output_folder, exist_ok=True)
        
        image_paths = []
        try:
            pdf_document = fitz.open(self.pdf_path)
            
            for page_index in range(len(pdf_document)):
                page = pdf_document[page_index]
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # 创建唯一的图像名称
                    image_filename = f"page{page_index+1}_img{img_index+1}.{image_ext}"
                    image_path = os.path.join(output_folder, image_filename)
                    
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    
                    image_paths.append({
                        "path": image_path,
                        "filename": image_filename,
                        "page": page_index
                    })
                    
            pdf_document.close()
            return image_paths
            
        except Exception as e:
            print(f"提取图片时出错: {str(e)}")
            return []


class OcrWorker(QThread):
    progress_updated = pyqtSignal(str)
    finished = pyqtSignal(dict, list)
    error = pyqtSignal(str)
    
    def __init__(self, file_path, api_key, model):
        super().__init__()
        self.file_path = file_path
        self.api_key = api_key
        self.model = model
        self.uploaded_file = None
        self.temp_image_folder = None
    
    def run(self):
        try:
            pdf_file = Path(self.file_path)
            client = Mistral(api_key=self.api_key)
            
            # 创建临时图片文件夹
            self.temp_image_folder = os.path.join(os.path.dirname(self.file_path), f"temp_images_{uuid.uuid4().hex}")
            os.makedirs(self.temp_image_folder, exist_ok=True)
            
            # 提取PDF中的图片
            self.progress_updated.emit("正在提取PDF中的图片...")
            extractor = PdfImageExtractor(self.file_path)
            extracted_images = extractor.extract_images(self.temp_image_folder)
            
            self.progress_updated.emit("上传文件中...")
            self.uploaded_file = client.files.upload(
                file={
                    "file_name": pdf_file.stem,
                    "content": pdf_file.read_bytes(),
                },
                purpose="ocr",
            )
            
            signed_url = client.files.get_signed_url(file_id=self.uploaded_file.id, expiry=1)
            
            self.progress_updated.emit(f"OCR处理中...")
            pdf_response = client.ocr.process(
                document=DocumentURLChunk(document_url=signed_url.url),
                model=self.model,
                include_image_base64=False,  # 降低API费用
            )
            
            response_dict = json.loads(pdf_response.model_dump_json())
            self.finished.emit(response_dict, extracted_images)
        
        except Exception as e:
            self.error.emit(str(e))
        finally:
            # 清理上传的文件
            try:
                if self.uploaded_file:
                    client.files.delete(file_id=self.uploaded_file.id)
                    self.progress_updated.emit("临时文件已删除")
            except Exception as e:
                self.progress_updated.emit(f"警告: 无法删除临时文件: {str(e)}")


class MistralOcrApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.response_data = None
        self.extracted_images = None
        self.output_folder = None
        
    def initUI(self):
        self.setWindowTitle("Mistral OCR")
        self.setMinimumSize(800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # API Key section
        api_key_group = QGroupBox("API 设置")
        api_key_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("输入Mistral API Key或使用环境变量MISTRAL_API_KEY")
        self.api_key_input.setText(os.environ.get("MISTRAL_API_KEY", ""))
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_layout.addWidget(QLabel("API Key:"))
        api_key_layout.addWidget(self.api_key_input)
        api_key_group.setLayout(api_key_layout)
        main_layout.addWidget(api_key_group)
        
        # File selection
        file_group = QGroupBox("文件选择")
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("未选择文件")
        self.file_path_label.setWordWrap(True)
        select_file_btn = QPushButton("选择PDF文件")
        select_file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(select_file_btn)
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # Options
        options_group = QGroupBox("OCR 选项")
        options_layout = QVBoxLayout()
        
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("OCR 模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItem("mistral-ocr-latest", "mistral-ocr-latest")
        model_layout.addWidget(self.model_combo)
        options_layout.addLayout(model_layout)
        
        # Output format options
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("输出格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Markdown", "HTML", "JSON"])
        format_layout.addWidget(self.format_combo)
        options_layout.addLayout(format_layout)
        
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)
        
        # Process button and progress
        process_layout = QHBoxLayout()
        self.process_btn = QPushButton("处理文档")
        self.process_btn.clicked.connect(self.process_document)
        self.process_btn.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        process_layout.addWidget(self.process_btn)
        process_layout.addWidget(self.progress_bar)
        main_layout.addLayout(process_layout)
        
        # Save options
        save_group = QGroupBox("保存选项")
        save_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存结果")
        self.save_btn.clicked.connect(self.save_result)
        self.save_btn.setEnabled(False)
        save_layout.addWidget(self.save_btn)
        save_group.setLayout(save_layout)
        main_layout.addWidget(save_group)
        
        # Results area with tabs for preview and raw data
        results_tabs = QTabWidget()
        
        # Preview tab
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        results_tabs.addTab(self.preview_text, "预览")
        
        # Raw tab
        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setFont(QFont("Courier New", 10))
        results_tabs.addTab(self.raw_text, "原始数据")
        
        main_layout.addWidget(results_tabs, 1)
        
        # 添加作者信息
        author_label = QLabel("by Lei Da (David)  Contact: greatradar@gmail.com")
        author_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        author_label.setStyleSheet("color: #666; margin: 5px;")
        main_layout.addWidget(author_label)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("准备就绪")
        
        self.setCentralWidget(main_widget)
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择PDF文件", "", "PDF Files (*.pdf)"
        )
        
        if file_path:
            self.file_path_label.setText(file_path)
            self.process_btn.setEnabled(True)
    
    def process_document(self):
        file_path = self.file_path_label.text()
        api_key = self.api_key_input.text()
        
        if not file_path or file_path == "未选择文件":
            QMessageBox.warning(self, "错误", "请先选择一个PDF文件")
            return
        
        if not api_key:
            api_key = os.environ.get("MISTRAL_API_KEY")
            if not api_key:
                QMessageBox.warning(self, "错误", "请提供Mistral API Key")
                return
        
        model = self.model_combo.currentData()
        
        # Disable UI elements during processing
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("处理中...")
        
        # Start OCR in a separate thread
        self.worker = OcrWorker(file_path, api_key, model)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(self.handle_results)
        self.worker.error.connect(self.handle_error)
        self.worker.start()
    
    def update_progress(self, message):
        self.status_bar.showMessage(message)
    
    def handle_results(self, response_dict, extracted_images):
        self.response_data = response_dict
        self.extracted_images = extracted_images
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        
        # Display raw JSON in the raw tab
        self.raw_text.setText(json.dumps(response_dict, indent=4, ensure_ascii=False))
        
        # Process and display content based on selected format
        output_format = self.format_combo.currentText().lower()
        
        # 生成预览（不创建实际文件）
        self.preview_content(output_format)
        
        self.status_bar.showMessage("处理完成")
    
    def preview_content(self, output_format):
        # 这只是预览，不创建实际文件和图片文件夹
        # 连接markdown内容（来自所有页面）
        markdown_contents = [
            page.get("markdown", "") for page in self.response_data.get("pages", [])
        ]
        markdown_text = "\n\n".join(markdown_contents)
        
        # 使用从PDF提取的图片进行预览
        image_map = {}
        for page_idx, page in enumerate(self.response_data.get("pages", [])):
            page_extracted_images = [img for img in self.extracted_images if img["page"] == page_idx]
            
            for img_idx, img in enumerate(page.get("images", [])):
                if "id" in img and img_idx < len(page_extracted_images):
                    image_id = img["id"]
                    image_path = page_extracted_images[img_idx]["path"]
                    
                    # 读取图片并转换为base64进行预览
                    try:
                        with open(image_path, "rb") as img_file:
                            img_data = img_file.read()
                            img_b64 = base64.b64encode(img_data).decode('utf-8')
                            
                            # 确定MIME类型
                            file_ext = image_path.split(".")[-1].lower()
                            mime_type = f"image/{file_ext}"
                            data_uri = f"data:{mime_type};base64,{img_b64}"
                            
                            image_map[image_id] = data_uri
                    except Exception as e:
                        print(f"预览图片时出错 {image_id}: {str(e)}")
        
        # 替换markdown中的图片引用
        for img_id, img_src in image_map.items():
            markdown_text = re.sub(
                r"!\[(.*?)\]\(" + re.escape(img_id) + r"\)",
                r"![\1](" + img_src + r")",
                markdown_text,
            )
        
        if output_format == "html":
            # 将markdown转换为HTML
            md = markdown.Markdown(extensions=["tables"])
            html_content = md.convert(markdown_text)
            
            # 添加最小HTML包装
            result = f"""<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>OCR Result</title>
                    <style>
                        body {{ 
                            font-family: Arial, sans-serif;
                            line-height: 1.6;
                            margin: 0 auto;
                            max-width: 800px;
                            padding: 20px;
                        }}
                        img {{ max-width: 100%; height: auto; }}
                        h1, h2, h3 {{ margin-top: 1.5em; }}
                        p {{ margin: 1em 0; }}
                    </style>
                </head>
                <body>
                {html_content}
                </body>
                </html>"""
            self.preview_text.setHtml(result)
        elif output_format == "json":
            self.preview_text.setPlainText(json.dumps(self.response_data, indent=4, ensure_ascii=False))
        else:  # markdown
            self.preview_text.setPlainText(markdown_text)
    
    def handle_error(self, error_message):
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"处理过程中出错: {error_message}")
        self.status_bar.showMessage("处理失败")


    def save_result(self):
        if not self.response_data:
            QMessageBox.warning(self, "警告", "没有要保存的结果")
            return
        
        # 选择保存目录而不是文件
        output_dir = QFileDialog.getExistingDirectory(
            self, "选择保存目录", "",
            options=QFileDialog.Option.ShowDirsOnly
        )
        
        if not output_dir:
            return
        
        self.output_folder = output_dir
        
        # 创建图片文件夹
        images_folder = os.path.join(output_dir, "images")
        os.makedirs(images_folder, exist_ok=True)
        
        # 复制已提取的图片到目标文件夹
        for img_info in self.extracted_images:
            try:
                src_path = img_info["path"]
                dest_path = os.path.join(images_folder, img_info["filename"])
                shutil.copy2(src_path, dest_path)
            except Exception as e:
                self.status_bar.showMessage(f"复制图片时出错: {str(e)}")
        
        # 根据选择的格式保存内容
        output_format = self.format_combo.currentText().lower()
        
        # 确定正确的文件扩展名
        if output_format == "markdown":
            file_ext = "md"  # 对markdown使用.md扩展名
        else:
            file_ext = output_format  # html和json保持不变
        
        output_file = os.path.join(output_dir, f"ocr_result.{file_ext}")
        
        # 收集每页中的所有图片ID和原始markdown
        page_markdowns = []
        image_ids_by_page = []
        
        for page in self.response_data.get("pages", []):
            # 收集这个页面上的所有图片ID
            page_img_ids = []
            for img in page.get("images", []):
                if "id" in img:
                    page_img_ids.append(img["id"])
            
            image_ids_by_page.append(page_img_ids)
            page_markdowns.append(page.get("markdown", ""))
        
        # 处理每页的markdown，替换图片引用
        updated_markdowns = []
        
        for page_idx, (page_md, page_img_ids) in enumerate(zip(page_markdowns, image_ids_by_page)):
            updated_md = page_md
            
            # 找出对应这个页面的提取图片
            page_extracted_images = [img for img in self.extracted_images if img["page"] == page_idx]
            
            # 为这个页面的每个图片ID创建替换
            for img_idx, img_id in enumerate(page_img_ids):
                if img_idx < len(page_extracted_images):
                    # 获取对应的提取图片文件名
                    img_filename = page_extracted_images[img_idx]["filename"]
                    new_img_path = f"images/{img_filename}"
                    
                    # 查找并替换markdown中的图片引用
                    pattern = r'!\[(.*?)\]\(' + re.escape(img_id) + r'\)'
                    replacement = r'![\1](' + new_img_path + r')'
                    updated_md = re.sub(pattern, replacement, updated_md)
                    
                    # 打印调试信息
                    print(f"替换页面 {page_idx+1} 图片: {img_id} -> {new_img_path}")
            
            updated_markdowns.append(updated_md)
        
        # 连接所有更新后的markdown内容
        markdown_text = "\n\n".join(updated_markdowns)
        
        # 打印最终的markdown文本以进行验证
        print("最终的markdown文本:")
        print(markdown_text)
        
        if output_format == "html":
            # 将markdown转换为HTML
            md = markdown.Markdown(extensions=["tables"])
            html_content = md.convert(markdown_text)
            
            # 添加HTML包装
            result = f"""<!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>OCR Result</title>
                <style>
                    body {{ 
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        margin: 0 auto;
                        max-width: 800px;
                        padding: 20px;
                    }}
                    img {{ max-width: 100%; height: auto; }}
                    h1, h2, h3 {{ margin-top: 1.5em; }}
                    p {{ margin: 1em 0; }}
                </style>
            </head>
            <body>
            {html_content}
            <hr>
            <p style="text-align: right; color: #666; font-size: 0.8em;">
                Generated by Mistral OCR App | by Lei Da (David) | greatradar@gmail.com
            </p>
            </body>
            </html>"""
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
        elif output_format == "json":
            # 为JSON添加提取的图片路径信息
            json_data = self.response_data.copy()
            # 在JSON中也更新图片路径
            for page_idx, page in enumerate(json_data.get("pages", [])):
                page_extracted_images = [img for img in self.extracted_images if img["page"] == page_idx]
                for img_idx, img in enumerate(page.get("images", [])):
                    if img_idx < len(page_extracted_images):
                        img_filename = page_extracted_images[img_idx]["filename"]
                        img["local_path"] = f"images/{img_filename}"
            
            # 添加元数据信息，包括作者信息
            json_data["metadata"] = {
                "app": "Mistral OCR App",
                "author": "Lei Da (David)",
                "contact": "greatradar@gmail.com"
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)
        else:  # markdown
            # 在markdown文件末尾添加作者信息
            markdown_text += "\n\n---\n\n*Generated by Mistral OCR App | by Lei Da (David) | greatradar@gmail.com*"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown_text)
        
        self.status_bar.showMessage(f"已保存到 {output_file}")
        
        # 清理临时文件夹
        try:
            if hasattr(self.worker, 'temp_image_folder') and self.worker.temp_image_folder:
                shutil.rmtree(self.worker.temp_image_folder, ignore_errors=True)
        except Exception as e:
            self.status_bar.showMessage(f"警告: 清理临时文件时出错: {str(e)}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Modern look across platforms
    window = MistralOcrApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
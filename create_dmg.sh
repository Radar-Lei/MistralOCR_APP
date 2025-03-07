brew install create-dmg
create-dmg \
  --volname "Mistral OCR" \
  --volicon "app_icon.icns" \
  --window-pos 200 120 \
  --window-size 600 300 \
  --icon-size 100 \
  --icon "Mistral OCR.app" 175 120 \
  --hide-extension "Mistral OCR.app" \
  --app-drop-link 425 120 \
  "MistralOCR.dmg" \
  "dist/Mistral OCR.app"
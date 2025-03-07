# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os.path

#
# 设置 DMG 配置
#

# New simplified dmgbuild_settings.py
application = defines.get('app', 'dist/Mistral OCR.app')
appname = os.path.basename(application)

# Basic configuration
format = defines.get('format', 'UDBZ')
size = defines.get('size', None)
files = [application]
symlinks = {'Applications': '/Applications'}
badge_icon = 'icons/OCRicon.icns'  # Direct path instead of extracting from plist
icon_locations = {
    appname: (140, 120),
    'Applications': (500, 120)
}

# Window configuration
background = 'builtin-arrow'
window_rect = ((100, 100), (640, 280))
title = defines.get('title', 'Mistral OCR')
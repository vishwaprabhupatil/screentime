[app]
title = Screentime
package.name = screentime
package.domain = org.example
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,xml,txt
source.include_patterns = Service/*

# Main entry point
entrypoint = main.py

# Requirements
requirements = python3,kivy,requests

# App version
version = 0.1

# Android settings
android.archs = armeabi-v7a, arm64-v8a
android.api = 33
android.minapi = 21

# Register background service
android.services = screentime_service:Service/service_main.py

# Permissions
android.permissions = INTERNET
android.permissions = FOREGROUND_SERVICE

log_level = 2
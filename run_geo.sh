#!/bin/bash
# GEO系统运行器 — 使用正确的Python环境
cd /home/judy/.hermes/projects/geo-system
exec /home/judy/.hermes/hermes-agent/venv/bin/python3 run_geo.py "$@"

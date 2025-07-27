#!/bin/bash

# Run streamlit in background
streamlit run /app/ui.py &

# Run MCP tool (this keeps the container alive)
python /app/mcp_tool.py
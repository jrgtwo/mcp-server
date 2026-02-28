from __future__ import annotations

from fastmcp import FastMCP

from model import state


def register(mcp: FastMCP) -> None:
    @mcp.resource("llm://info")
    def model_info() -> str:
        """Metadata about the currently loaded model."""
        if state.model is None:
            return "Model not loaded."

        param = next(state.model.parameters())
        total_params = sum(p.numel() for p in state.model.parameters())
        return "\n".join([
            f"path:       {state.model_path}",
            f"device:     {state.device}",
            f"dtype:      {param.dtype}",
            f"parameters: {total_params / 1e9:.2f}B",
        ])

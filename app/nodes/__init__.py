"""
Node Plugins Package - Auto-registers all core and extended nodes
"""
import app.nodes.assets
import app.nodes.routing
import app.nodes.generation
import app.nodes.postprocess

__all__ = ["assets", "routing", "generation", "postprocess"]

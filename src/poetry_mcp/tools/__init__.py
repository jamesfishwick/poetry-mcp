"""MCP tools for catalog, nexus, submission, chain, and similarity management."""

from .chain_tools import (
    initialize_chain_tools,
    create_chain,
    add_poems_to_chain,
    remove_poems_from_chain,
    reorder_chain,
    delete_chain,
    get_chain,
    list_chains,
)
from .similarity_tools import (
    initialize_similarity_tools,
    find_similar_poems,
)

__all__ = [
    "initialize_chain_tools",
    "create_chain",
    "add_poems_to_chain",
    "remove_poems_from_chain",
    "reorder_chain",
    "delete_chain",
    "get_chain",
    "list_chains",
    "initialize_similarity_tools",
    "find_similar_poems",
]

"""Dropshipping Winner Intelligence & Prospecting System (hunter module)."""

__version__ = "1.0.0"

def __getattr__(name: str):
    if name == "AuditEngine":
        from hunter.audit_engine import AuditEngine
        return AuditEngine
    if name == "DossierGenerator":
        from hunter.dossier_generator import DossierGenerator
        return DossierGenerator
    if name == "HunterEngine":
        from hunter.hunter_engine import HunterEngine
        return HunterEngine
    if name == "Visualizer":
        from hunter.visualizer import Visualizer
        return Visualizer
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = ["AuditEngine", "DossierGenerator", "HunterEngine", "Visualizer", "__version__"]

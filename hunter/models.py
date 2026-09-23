"""Data models and serialization contracts for Dropshipping Hunter.

Strictly conforms to PROJECT.md § Interface Contracts:
- RawCandidate (M1 ↔ M2 exchange contract)
- FinancialMetrics (Unit economics calculation contract)
- RuleScore (7 Golden Rules operational subscore contract)
- AuditResult (M2 ↔ M3, M4 evaluation report contract)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class RawCandidate:
    """Raw product candidate extracted across intelligence sources."""
    candidate_id: str                      # Unique slug/ID (e.g. 'spinerelief-pro')
    name: str                              # Product title
    category: str                          # Niche category (e.g. 'Health & Ergonomics')
    description: str                       # Detailed functional description
    supplier_cost: float                   # Landed supplier CoGS in USD
    shipping_cost: float                   # Estimated tracked shipping in USD
    suggested_price: float                 # Target retail price (SRP) in USD
    shipping_days_min: int                 # Minimum delivery days (e.g. 7)
    shipping_days_max: int                 # Maximum delivery days (e.g. 12)
    shipping_carrier: str                  # Carrier name (e.g. 'YunExpress')
    has_fragile_material: bool             # True if thin glass/porcelain
    has_sizing_requirements: bool          # True if millimetric clothing sizing
    demo_visual_speed_sec: float           # Seconds to demonstrate transformation (e.g. 1.5)
    pain_level_score: float                # 0-100 score on pain intensity
    retail_availability_score: float       # 0-100 score on absence from retail (higher = more scarce)
    ad_active_days: int                    # Days ad has been running continuously
    competitor_ad_count: int               # Number of active competitor ads
    google_trends_momentum: float          # 3-month growth rate percentage (e.g. +45.0)
    source_url: str                        # Supplier or ad intelligence URL
    target_demographics: Dict[str, Any] = field(default_factory=dict)  # Age, gender, occupations

    def validate(self) -> List[str]:
        """Validate candidate fields against expected bounds and types.
        
        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []
        if not self.candidate_id or not isinstance(self.candidate_id, str):
            errors.append("candidate_id must be a non-empty string")
        if not self.name or not isinstance(self.name, str):
            errors.append("name must be a non-empty string")
        if self.supplier_cost < 0:
            errors.append(f"supplier_cost cannot be negative: {self.supplier_cost}")
        if self.shipping_cost < 0:
            errors.append(f"shipping_cost cannot be negative: {self.shipping_cost}")
        if self.suggested_price <= 0:
            errors.append(f"suggested_price must be positive: {self.suggested_price}")
        if self.shipping_days_min < 0 or self.shipping_days_max < self.shipping_days_min:
            errors.append(f"Invalid shipping window: {self.shipping_days_min}-{self.shipping_days_max} days")
        if not (0.0 <= self.pain_level_score <= 100.0):
            errors.append(f"pain_level_score must be between 0 and 100: {self.pain_level_score}")
        if not (0.0 <= self.retail_availability_score <= 100.0):
            errors.append(f"retail_availability_score must be between 0 and 100: {self.retail_availability_score}")
        if self.demo_visual_speed_sec < 0:
            errors.append(f"demo_visual_speed_sec cannot be negative: {self.demo_visual_speed_sec}")
        if self.ad_active_days < 0:
            errors.append(f"ad_active_days cannot be negative: {self.ad_active_days}")
        return errors

    def compute_financials(self) -> FinancialMetrics:
        """Calculate unit economics according to Antigravity canonical standards.
        
        Processor fee = (SRP * 0.029) + $0.30
        Reserve buffer = SRP * 0.01
        Landed cost = supplier_cost + shipping_cost
        Markup = SRP / Landed cost
        Net Profit = SRP - Landed cost - Processor fee - Reserve buffer
        Net Margin % = (Net Profit / SRP) * 100.0
        """
        landed = round(self.supplier_cost + self.shipping_cost, 2)
        srp = round(self.suggested_price, 2)
        markup = round(srp / landed, 2) if landed > 0 else 0.0
        processor_fee = round((srp * 0.029) + 0.30, 2)
        reserve_buffer = round(srp * 0.01, 2)
        net_profit = round(srp - landed - processor_fee - reserve_buffer, 2)
        net_margin_pct = round((net_profit / srp) * 100.0, 2) if srp > 0 else 0.0

        return FinancialMetrics(
            landed_cost=landed,
            srp=srp,
            markup_multiplier=markup,
            processor_fee=processor_fee,
            reserve_buffer=reserve_buffer,
            net_profit=net_profit,
            net_margin_pct=net_margin_pct,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to standard Python dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RawCandidate:
        """Create RawCandidate instance from dictionary, coercing types."""
        return cls(
            candidate_id=str(data.get("candidate_id", "")),
            name=str(data.get("name", "")),
            category=str(data.get("category", "")),
            description=str(data.get("description", "")),
            supplier_cost=float(data.get("supplier_cost", 0.0)),
            shipping_cost=float(data.get("shipping_cost", 0.0)),
            suggested_price=float(data.get("suggested_price", 0.0)),
            shipping_days_min=int(data.get("shipping_days_min", 0)),
            shipping_days_max=int(data.get("shipping_days_max", 0)),
            shipping_carrier=str(data.get("shipping_carrier", "")),
            has_fragile_material=bool(data.get("has_fragile_material", False)),
            has_sizing_requirements=bool(data.get("has_sizing_requirements", False)),
            demo_visual_speed_sec=float(data.get("demo_visual_speed_sec", 0.0)),
            pain_level_score=float(data.get("pain_level_score", 0.0)),
            retail_availability_score=float(data.get("retail_availability_score", 0.0)),
            ad_active_days=int(data.get("ad_active_days", 0)),
            competitor_ad_count=int(data.get("competitor_ad_count", 0)),
            google_trends_momentum=float(data.get("google_trends_momentum", 0.0)),
            source_url=str(data.get("source_url", "")),
            target_demographics=dict(data.get("target_demographics", {})),
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialize candidate to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> RawCandidate:
        """Deserialize candidate from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class FinancialMetrics:
    """Unit economics and margin breakdown under organic traffic ($0 ad spend)."""
    landed_cost: float                     # supplier_cost + shipping_cost
    srp: float                             # Suggested retail price
    markup_multiplier: float               # srp / landed_cost
    processor_fee: float                   # (srp * 0.029) + 0.30
    reserve_buffer: float                  # srp * 0.01
    net_profit: float                      # srp - landed_cost - processor_fee - reserve_buffer
    net_margin_pct: float                  # (net_profit / srp) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FinancialMetrics:
        """Create FinancialMetrics from dictionary."""
        return cls(
            landed_cost=float(data.get("landed_cost", 0.0)),
            srp=float(data.get("srp", 0.0)),
            markup_multiplier=float(data.get("markup_multiplier", 0.0)),
            processor_fee=float(data.get("processor_fee", 0.0)),
            reserve_buffer=float(data.get("reserve_buffer", 0.0)),
            net_profit=float(data.get("net_profit", 0.0)),
            net_margin_pct=float(data.get("net_margin_pct", 0.0)),
        )


@dataclass
class RuleScore:
    """Evaluation score for an individual Golden Rule (Rules 1 to 7)."""
    rule_id: int                           # 1 to 7
    name: str                              # Rule name
    raw_score: float                       # 0 to 100
    weight: float                          # Weight (0.10 or 0.20)
    weighted_score: float                  # raw_score * weight
    passed: bool                           # True if raw_score >= 60.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RuleScore:
        """Create RuleScore from dictionary."""
        return cls(
            rule_id=int(data.get("rule_id", 0)),
            name=str(data.get("name", "")),
            raw_score=float(data.get("raw_score", 0.0)),
            weight=float(data.get("weight", 0.0)),
            weighted_score=float(data.get("weighted_score", 0.0)),
            passed=bool(data.get("passed", False)),
        )


@dataclass
class AuditResult:
    """Full audit result for a candidate evaluated across the 7 Golden Rules."""
    candidate: RawCandidate
    financials: FinancialMetrics
    rule_scores: Dict[int, RuleScore]      # 1..7 mapping
    ko_gates_tripped: List[str]            # Empty if all passed; e.g. ["KO-1"]
    composite_score: float                 # 0 to 100
    tier: str                              # "WINNER", "CONTENDER", "DISQUALIFIED"
    passed_audit: bool                     # True if tier == "WINNER"

    def to_dict(self) -> Dict[str, Any]:
        """Convert AuditResult to nested dictionary."""
        return {
            "candidate": self.candidate.to_dict(),
            "financials": self.financials.to_dict(),
            "rule_scores": {str(k): v.to_dict() for k, v in self.rule_scores.items()},
            "ko_gates_tripped": list(self.ko_gates_tripped),
            "composite_score": self.composite_score,
            "tier": self.tier,
            "passed_audit": self.passed_audit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AuditResult:
        """Construct AuditResult from nested dictionary."""
        candidate = RawCandidate.from_dict(data.get("candidate", {}))
        financials = FinancialMetrics.from_dict(data.get("financials", {}))
        
        raw_scores = data.get("rule_scores", {})
        rule_scores: Dict[int, RuleScore] = {}
        for k, v in raw_scores.items():
            rule_id = int(k)
            rule_scores[rule_id] = RuleScore.from_dict(v) if isinstance(v, dict) else v

        return cls(
            candidate=candidate,
            financials=financials,
            rule_scores=rule_scores,
            ko_gates_tripped=list(data.get("ko_gates_tripped", [])),
            composite_score=float(data.get("composite_score", 0.0)),
            tier=str(data.get("tier", "DISQUALIFIED")),
            passed_audit=bool(data.get("passed_audit", False)),
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialize AuditResult to JSON."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> AuditResult:
        """Deserialize AuditResult from JSON string."""
        return cls.from_dict(json.loads(json_str))

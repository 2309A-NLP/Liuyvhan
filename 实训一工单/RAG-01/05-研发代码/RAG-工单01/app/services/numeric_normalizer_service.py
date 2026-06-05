import re
from decimal import Decimal, InvalidOperation


class NumericNormalizerService:
    AMOUNT_PATTERN = re.compile(r"(?P<number>\d[\d,]*(?:\.\d+)?)(?:\s*)(?P<unit>万亿元|亿元|万元|元)")
    PERCENT_PATTERN = re.compile(r"(?P<number>\d[\d,]*(?:\.\d+)?)(?:\s*)%")
    UNIT_TO_YUAN = {
        "万亿元": Decimal("1000000000000"),
        "亿元": Decimal("100000000"),
        "万元": Decimal("10000"),
        "元": Decimal("1"),
    }
    TARGET_UNITS = ("亿元", "万元", "元")

    def extract_numeric_aliases(self, text: str) -> list[str]:
        aliases: list[str] = []
        if not text:
            return aliases

        for match in self.AMOUNT_PATTERN.finditer(text):
            value = self._parse_decimal(match.group("number"))
            unit = match.group("unit")
            if value is None:
                continue

            yuan_value = value * self.UNIT_TO_YUAN[unit]
            self._append_unique(aliases, f"{self._format_decimal(value)}{unit}")

            for target_unit in self.TARGET_UNITS:
                converted = yuan_value / self.UNIT_TO_YUAN[target_unit]
                if target_unit == "元" and converted != converted.to_integral_value():
                    continue
                self._append_unique(aliases, f"{self._format_decimal(converted)}{target_unit}")

        for match in self.PERCENT_PATTERN.finditer(text):
            value = self._parse_decimal(match.group("number"))
            if value is None:
                continue
            self._append_unique(aliases, f"{self._format_decimal(value)}%")

        return aliases

    def _append_unique(self, aliases: list[str], alias: str) -> None:
        value = alias.strip()
        if value and value not in aliases:
            aliases.append(value)

    def _parse_decimal(self, raw_value: str) -> Decimal | None:
        try:
            return Decimal(raw_value.replace(",", "").strip())
        except (InvalidOperation, AttributeError):
            return None

    def _format_decimal(self, value: Decimal) -> str:
        normalized = format(value.normalize(), "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return normalized or "0"

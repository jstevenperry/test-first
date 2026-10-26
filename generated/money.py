from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def decimal_value(value):
    if isinstance(value, bool):
        raise ValueError("invalid monetary value")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid monetary value") from exc
    if not result.is_finite():
        raise ValueError("invalid monetary value")
    return result


def cents(value):
    amount = decimal_value(value)
    if amount < 0:
        raise ValueError("price must be non-negative")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def multiply(unit_price, quantity):
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValueError("quantity must be a non-negative whole number")
    return cents(decimal_value(unit_price) * quantity)


def format_cents(value):
    return f"{value // 100}.{value % 100:02d}"


def format_rate(basis_points):
    if isinstance(basis_points, bool) or not isinstance(basis_points, int):
        raise ValueError("rate must be integer basis points")
    return f"{Decimal(basis_points) / Decimal(100):.2f}"


def amount_at_rate(amount_cents, basis_points):
    if isinstance(basis_points, bool) or not isinstance(basis_points, int):
        raise ValueError("rate must be integer basis points")
    amount = (Decimal(amount_cents) * Decimal(basis_points) / Decimal(10000))
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def line_amounts(unit_price_cents, quantity, discount_rate_bps=0, tax_rate_bps=0):
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValueError("quantity must be a non-negative whole number")
    extended = unit_price_cents * quantity
    discount = amount_at_rate(extended, discount_rate_bps)
    subtotal = extended - discount
    tax = amount_at_rate(subtotal, tax_rate_bps)
    return {"extended": extended, "discount": discount, "subtotal": subtotal, "tax": tax}

"""Entidades validadas, independientes de servicios y de la interfaz."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

from .exceptions import StateError, StockError, ValidationError


_MAX_VALUE = Decimal("1000000000000")
_CENT = Decimal("0.01")
_LIMA = timezone(timedelta(hours=-5))
_MAX_ID_LENGTH = 100
_MAX_NAME_LENGTH = 120
_MAX_LABEL_LENGTH = 80
_MAX_NOTE_LENGTH = 1000
_PRODUCT_TYPES = ("DIRECTO", "PREPARADO_ANTICIPADO", "PREPARADO_INSTANTE")
_UNITS = ("g", "ml", "und")
_STATUSES = ("PENDIENTE", "PAGADO", "CANCELADO", "ANULADO")
_PREPARATIONS = ("PENDIENTE", "EN_PREPARACION", "LISTO", "ENTREGADO")


def _as_decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValidationError(f"{label} no puede ser un booleano.")
    if not isinstance(value, (Decimal, str, int, float)):
        raise ValidationError(f"{label} debe ser un numero valido.")
    try:
        if isinstance(value, Decimal):
            result = value
        elif isinstance(value, int):
            result = Decimal(value)
        else:
            text = str(value).strip().replace(",", ".")
            if "_" in text:
                raise InvalidOperation
            result = Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"{label} debe ser un numero valido.") from None
    if not result.is_finite():
        raise ValidationError(f"{label} debe ser un numero finito.")
    return result


def decimal_value(value, label="Cantidad", minimum=0) -> Decimal:
    result = _as_decimal(value, label)
    lower_bound = _as_decimal(minimum, "Minimo")
    if result < lower_bound:
        raise ValidationError(f"{label} debe ser mayor o igual a {lower_bound}.")
    if result > _MAX_VALUE:
        raise ValidationError(f"{label} no puede superar {_MAX_VALUE}.")
    if result:
        digits = result.as_tuple().digits
        trailing_zeros = 0
        for digit in reversed(digits):
            if digit:
                break
            trailing_zeros += 1
        if result.as_tuple().exponent + trailing_zeros < -6:
            raise ValidationError(f"{label} admite como maximo seis decimales significativos.")
    return result


def money(value) -> Decimal:
    result = decimal_value(value, "Monto")
    with localcontext(Context(prec=28)):
        return result.quantize(_CENT, rounding=ROUND_HALF_UP)


def _text(value: object, label: str, maximum: int, allow_empty=False) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} debe ser texto.")
    if len(value) > maximum:
        raise ValidationError(f"{label} no puede superar {maximum} caracteres.")
    result = value.strip()
    if not result and not allow_empty:
        raise ValidationError(f"{label} no puede estar vacio.")
    return result


def _enum(value: object, label: str, choices: tuple[str, ...]) -> str:
    result = _text(value, label, max(map(len, choices)))
    if result not in choices:
        raise ValidationError(f"{label} no es valido. Opciones: {', '.join(choices)}.")
    return result


def _active(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValidationError("Activo debe ser un booleano.")
    return value


def _whole_value(value: object, label: str, minimum=0) -> Decimal:
    result = decimal_value(value, label, minimum)
    if result != result.to_integral_value():
        raise ValidationError(f"{label} debe ser un numero entero.")
    return result


def _positive_money(value: object) -> Decimal:
    result = money(value)
    if result <= 0:
        raise ValidationError("El precio debe ser mayor que cero despues del redondeo.")
    return result


def _stock_after_change(stock: Decimal, delta: object, whole: bool) -> Decimal:
    if whole:
        change = _whole_value(delta, "Variacion de stock", -_MAX_VALUE)
    else:
        change = decimal_value(delta, "Variacion de stock", -_MAX_VALUE)
    if not change:
        return stock
    if not stock:
        result = change
    else:
        # Conserva todas las cifras de cantidades fraccionarias al sumar stock.
        exponent = min(stock.as_tuple().exponent, change.as_tuple().exponent)
        precision = max(28, max(stock.adjusted(), change.adjusted()) - exponent + 2)
        with localcontext(Context(prec=precision, Emin=min(-999999, exponent))):
            result = stock + change
    if result < 0:
        raise StockError("Stock insuficiente para realizar la operacion.")
    return decimal_value(result, "Stock")


def _record(data: object, required: tuple[str, ...], label: str) -> Mapping:
    if not isinstance(data, Mapping):
        raise ValidationError(f"{label} debe ser un diccionario.")
    for field in required:
        if field not in data:
            raise ValidationError(f"Falta el campo {field} en {label}.")
    return data


class Product:
    __slots__ = (
        "__id", "__name", "__category", "__price", "__product_type",
        "__stock", "__minimum_stock", "__recipe", "__active",
    )

    def __init__(self, id, name, category, price, product_type="DIRECTO", stock=0,
                 minimum_stock=0, recipe=None, active=True):
        self.__id = _text(id, "Identificador de producto", _MAX_ID_LENGTH)
        self.__name = _text(name, "Nombre de producto", _MAX_NAME_LENGTH)
        self.__category = _text(category, "Categoria", _MAX_LABEL_LENGTH)
        self.__price = _positive_money(price)
        self.__product_type = _enum(product_type, "Tipo de producto", _PRODUCT_TYPES)
        whole = self.__product_type != "PREPARADO_INSTANTE"
        self.__stock = (_whole_value(stock, "Stock") if whole
                        else decimal_value(stock, "Stock"))
        self.__minimum_stock = (_whole_value(minimum_stock, "Stock minimo") if whole
                                else decimal_value(minimum_stock, "Stock minimo"))
        if not whole and self.__stock != 0:
            raise ValidationError("Un producto preparado al instante debe tener stock cero.")
        if recipe is None:
            recipe = {}
        if not isinstance(recipe, Mapping):
            raise ValidationError("La receta debe ser un diccionario de ingredientes.")
        validated_recipe = {}
        for ingredient_id, quantity in recipe.items():
            key = _text(ingredient_id, "Identificador de ingrediente", _MAX_ID_LENGTH)
            if key in validated_recipe:
                raise ValidationError("La receta contiene un identificador repetido.")
            amount = decimal_value(quantity, "Cantidad de ingrediente")
            if amount <= 0:
                raise ValidationError("La cantidad de ingrediente debe ser mayor que cero.")
            validated_recipe[key] = amount
        if not whole and not validated_recipe:
            raise ValidationError("Un producto preparado al instante debe tener receta.")
        self.__recipe = validated_recipe
        self.__active = _active(active)

    @property
    def id(self) -> str:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name

    @property
    def category(self) -> str:
        return self.__category

    @property
    def price(self) -> Decimal:
        return self.__price

    @property
    def product_type(self) -> str:
        return self.__product_type

    @property
    def stock(self) -> Decimal:
        return self.__stock

    @property
    def minimum_stock(self) -> Decimal:
        return self.__minimum_stock

    @property
    def recipe(self) -> dict[str, Decimal]:
        return self.__recipe.copy()

    @property
    def active(self) -> bool:
        return self.__active

    def change_stock(self, delta):
        if self.__product_type == "PREPARADO_INSTANTE":
            change = decimal_value(delta, "Variacion de stock", -_MAX_VALUE)
            if change != 0:
                raise StockError("Los productos preparados al instante no tienen stock propio.")
            return
        self.__stock = _stock_after_change(self.__stock, delta, whole=True)

    def to_dict(self) -> dict:
        return {
            "id": self.__id,
            "name": self.__name,
            "category": self.__category,
            "price": str(self.__price),
            "product_type": self.__product_type,
            "stock": str(self.__stock),
            "minimum_stock": str(self.__minimum_stock),
            "recipe": {key: str(value) for key, value in self.__recipe.items()},
            "active": self.__active,
        }

    @classmethod
    def from_dict(cls, data) -> Product:
        data = _record(data, ("id", "name", "category", "price"), "Producto")
        return cls(
            id=data["id"], name=data["name"], category=data["category"],
            price=data["price"], product_type=data.get("product_type", "DIRECTO"),
            stock=data.get("stock", 0), minimum_stock=data.get("minimum_stock", 0),
            recipe=data.get("recipe"), active=data.get("active", True),
        )


class Ingredient:
    __slots__ = ("__id", "__name", "__unit", "__stock", "__minimum_stock", "__active")

    def __init__(self, id, name, unit, stock=0, minimum_stock=0, active=True):
        self.__id = _text(id, "Identificador de ingrediente", _MAX_ID_LENGTH)
        self.__name = _text(name, "Nombre de ingrediente", _MAX_NAME_LENGTH)
        self.__unit = _enum(unit, "Unidad", _UNITS)
        whole = self.__unit == "und"
        self.__stock = (_whole_value(stock, "Stock") if whole
                        else decimal_value(stock, "Stock"))
        self.__minimum_stock = (_whole_value(minimum_stock, "Stock minimo") if whole
                                else decimal_value(minimum_stock, "Stock minimo"))
        self.__active = _active(active)

    @property
    def id(self) -> str:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name

    @property
    def unit(self) -> str:
        return self.__unit

    @property
    def stock(self) -> Decimal:
        return self.__stock

    @property
    def minimum_stock(self) -> Decimal:
        return self.__minimum_stock

    @property
    def active(self) -> bool:
        return self.__active

    def change_stock(self, delta):
        self.__stock = _stock_after_change(self.__stock, delta, whole=self.__unit == "und")

    def to_dict(self) -> dict:
        return {
            "id": self.__id,
            "name": self.__name,
            "unit": self.__unit,
            "stock": str(self.__stock),
            "minimum_stock": str(self.__minimum_stock),
            "active": self.__active,
        }

    @classmethod
    def from_dict(cls, data) -> Ingredient:
        data = _record(data, ("id", "name", "unit"), "Ingrediente")
        return cls(
            id=data["id"], name=data["name"], unit=data["unit"],
            stock=data.get("stock", 0), minimum_stock=data.get("minimum_stock", 0),
            active=data.get("active", True),
        )


class OrderLine:
    __slots__ = ("__product_id", "__product_name", "__quantity", "__unit_price")

    def __init__(self, product_id, product_name, quantity, unit_price):
        self.__product_id = _text(product_id, "Identificador de producto", _MAX_ID_LENGTH)
        self.__product_name = _text(product_name, "Nombre de producto", _MAX_NAME_LENGTH)
        self.__quantity = int(_whole_value(quantity, "Cantidad", minimum=1))
        self.__unit_price = _positive_money(unit_price)

    @property
    def product_id(self) -> str:
        return self.__product_id

    @property
    def product_name(self) -> str:
        return self.__product_name

    @property
    def quantity(self) -> int:
        return self.__quantity

    @property
    def unit_price(self) -> Decimal:
        return self.__unit_price

    @property
    def subtotal(self) -> Decimal:
        with localcontext(Context(prec=28)):
            return self.__unit_price * self.__quantity

    def to_dict(self) -> dict:
        return {
            "product_id": self.__product_id,
            "product_name": self.__product_name,
            "quantity": self.__quantity,
            "unit_price": str(self.__unit_price),
            "subtotal": str(self.subtotal),
        }

    @classmethod
    def from_dict(cls, data) -> OrderLine:
        data = _record(data, ("product_id", "product_name", "quantity", "unit_price"),
                       "Linea de pedido")
        return cls(
            product_id=data["product_id"], product_name=data["product_name"],
            quantity=data["quantity"], unit_price=data["unit_price"],
        )


def _order_lines(lines: object) -> tuple[OrderLine, ...]:
    if not isinstance(lines, Iterable) or isinstance(lines, (str, bytes, Mapping)):
        raise ValidationError("Las lineas deben ser una coleccion de OrderLine.")
    result = tuple(lines)
    if not result:
        raise ValidationError("Un pedido debe tener al menos una linea.")
    if not all(isinstance(line, OrderLine) for line in result):
        raise ValidationError("Cada linea del pedido debe ser un OrderLine.")
    return result


class Order:
    __slots__ = (
        "__id", "__user_id", "__lines", "__table", "__guests", "__note",
        "__status", "__preparation", "__created_at",
    )

    def __init__(self, id, user_id, lines, table="PARA LLEVAR", guests=1, note="",
                 status="PENDIENTE", preparation="PENDIENTE", created_at=None):
        self.__id = _text(id, "Identificador de pedido", _MAX_ID_LENGTH)
        self.__user_id = _text(user_id, "Identificador de usuario", _MAX_ID_LENGTH)
        self.__lines = _order_lines(lines)
        self.__table = _text(table, "Mesa", _MAX_LABEL_LENGTH)
        self.__guests = int(_whole_value(guests, "Comensales", minimum=1))
        self.__note = _text(note, "Nota", _MAX_NOTE_LENGTH, allow_empty=True)
        self.__status = _enum(status, "Estado de pedido", _STATUSES)
        self.__preparation = _enum(preparation, "Estado de preparacion", _PREPARATIONS)
        if created_at is None:
            timestamp = datetime.now(_LIMA)
        elif isinstance(created_at, datetime):
            timestamp = created_at
        elif isinstance(created_at, str):
            value = _text(created_at, "Fecha de creacion", 80)
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            try:
                timestamp = datetime.fromisoformat(value)
            except ValueError:
                raise ValidationError("La fecha de creacion debe tener formato ISO valido.") from None
        else:
            raise ValidationError("La fecha de creacion debe ser una fecha ISO con zona horaria.")
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValidationError("La fecha de creacion debe incluir zona horaria.")
        try:
            self.__created_at = timestamp.astimezone(_LIMA).isoformat()
        except (ValueError, OverflowError):
            raise ValidationError("La fecha de creacion esta fuera del rango permitido.") from None

    @property
    def id(self) -> str:
        return self.__id

    @property
    def user_id(self) -> str:
        return self.__user_id

    @property
    def lines(self) -> tuple[OrderLine, ...]:
        return self.__lines

    @property
    def table(self) -> str:
        return self.__table

    @property
    def guests(self) -> int:
        return self.__guests

    @property
    def note(self) -> str:
        return self.__note

    @property
    def status(self) -> str:
        return self.__status

    @property
    def preparation(self) -> str:
        return self.__preparation

    @property
    def created_at(self) -> str:
        return self.__created_at

    @property
    def total(self) -> Decimal:
        with localcontext(Context(prec=28 + len(str(len(self.__lines))))):
            return sum((line.subtotal for line in self.__lines), Decimal("0.00"))

    def transition(self, status):
        target = _enum(status, "Estado de pedido", _STATUSES)
        allowed = {
            "PENDIENTE": ("PAGADO", "CANCELADO"),
            "PAGADO": ("ANULADO",),
            "CANCELADO": (),
            "ANULADO": (),
        }
        if target not in allowed[self.__status]:
            raise StateError(f"No se puede cambiar un pedido de {self.__status} a {target}.")
        self.__status = target

    def set_preparation(self, preparation):
        target = _enum(preparation, "Estado de preparacion", _PREPARATIONS)
        if self.__status in ("CANCELADO", "ANULADO"):
            raise StateError("No se puede preparar un pedido cancelado o anulado.")
        current_index = _PREPARATIONS.index(self.__preparation)
        if _PREPARATIONS.index(target) != current_index + 1:
            raise StateError("La preparacion solo puede avanzar a la siguiente etapa.")
        self.__preparation = target

    def replace_lines(self, lines, note=None):
        if self.__status != "PENDIENTE":
            raise StateError("Solo se pueden editar pedidos pendientes.")
        new_lines = _order_lines(lines)
        new_note = (self.__note if note is None
                    else _text(note, "Nota", _MAX_NOTE_LENGTH, allow_empty=True))
        self.__lines = new_lines
        self.__note = new_note

    def to_dict(self) -> dict:
        return {
            "id": self.__id,
            "user_id": self.__user_id,
            "lines": [line.to_dict() for line in self.__lines],
            "table": self.__table,
            "guests": self.__guests,
            "note": self.__note,
            "status": self.__status,
            "preparation": self.__preparation,
            "created_at": self.__created_at,
            "total": str(self.total),
        }

    @classmethod
    def from_dict(cls, data) -> Order:
        data = _record(data, ("id", "user_id", "lines"), "Pedido")
        if not isinstance(data["lines"], (list, tuple)):
            raise ValidationError("Las lineas serializadas deben ser una lista.")
        return cls(
            id=data["id"], user_id=data["user_id"],
            lines=[OrderLine.from_dict(line) for line in data["lines"]],
            table=data.get("table", "PARA LLEVAR"), guests=data.get("guests", 1),
            note=data.get("note", ""), status=data.get("status", "PENDIENTE"),
            preparation=data.get("preparation", "PENDIENTE"),
            created_at=data.get("created_at"),
        )

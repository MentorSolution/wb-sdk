"""WB report data aggregation functions for testing transform parameter."""

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AggregatedRow:
    """Aggregated report row with memory-efficient slots."""

    client: str = ""
    article_seller: str = ""
    predmet: str = ""
    size: str = ""
    article_wb: str = "0"
    delivery_amount: float = 0.0
    return_amount: float = 0.0
    summ_sales: float = 0.0
    summ_returns: float = 0.0
    retail_price_withdisc_rub: float = 0.0
    cashback_discount: float = 0.0
    cashback_commission_change: float = 0.0
    sales: float = 0.0
    goods_return: float = 0.0
    kompensation: float = 0.0
    korrect_sales: float = 0.0
    equaring: float = 0.0
    avans: float = 0.0
    brak: float = 0.0
    return_avans: float = 0.0
    return_brak: float = 0.0
    korrect_sales_returns: float = 0.0
    returns: float = 0.0
    additional_payment: float = 0.0
    penalty: float = 0.0
    logistics: float = 0.0
    correction_logistics: float = 0.0
    kompensation_returns: float = 0.0
    storno_logistics: float = 0.0
    storno_returns: float = 0.0
    logistics_returns: float = 0.0
    kompensation_logistics: float = 0.0
    itog_sales: float = 0.0
    int_ad: float = 0.0
    ext_ad: float = 0.0
    deduction: float = 0.0
    storage_fee: float = 0.0
    storage_fee_recost: float = 0.0
    acceptance: float = 0.0
    kompensation_priemki: float = 0.0
    goods_return_return: float = 0.0
    commission_percent: float = 0.0
    deduction_internal_ad: float = 0.0
    deduction_credit: float = 0.0
    deduction_jem: float = 0.0
    pvz_compensation: float = 0.0
    loyalty_discount_compensation: float = 0.0
    goods_processing: float = 0.0
    loyalty_program_cost: float = 0.0
    loyalty_points_deduction: float = 0.0


def aggregate_rows_by_size_and_totals(
    full_report: list[dict[str, Any]],
) -> tuple[list[AggregatedRow], dict[str, float]]:
    """Aggregate WB report rows by size and calculate totals."""
    rows: dict[tuple[str, str], AggregatedRow] = {}
    tot: defaultdict[str, float] = defaultdict(float)

    for rep in full_report:
        _process_single_row(rep, rows, tot)

    tot["deduction"] = tot.get("deduction_raw", 0.0)

    totals = {
        "storage_fee": tot.get("storage_fee", 0.0),
        "deduction": tot.get("deduction", 0.0),
        "penalty": tot.get("penalty", 0.0),
        "acceptance": tot.get("acceptance", 0.0),
        "kompensation_priemki": tot.get("kompensation_priemki", 0.0),
        "penalty_total": tot.get("penalty", 0.0),
        "internal_ad_total": tot.get("internal_ad_total", 0.0),
        "credit_payment_total": tot.get("credit_payment_total", 0.0),
        "jem_total": tot.get("jem_total", 0.0),
        "pvz_compensation": tot.get("pvz_compensation", 0.0),
        "loyalty_discount_compensation": tot.get("loyalty_discount_compensation", 0.0),
        "goods_processing": tot.get("goods_processing", 0.0),
        "loyalty_program_cost": tot.get("loyalty_program_cost", 0.0),
        "loyalty_points_deduction": tot.get("loyalty_points_deduction", 0.0),
    }

    return list(rows.values()), totals


def _process_single_row(
    rep: dict[str, Any],
    rows: dict[tuple[str, str], AggregatedRow],
    tot: defaultdict[str, float],
) -> None:
    """Process a single report row and update aggregation state in place."""
    sa = str(rep.get("sa_name", "") or "")
    size = str(rep.get("ts_name", "") or "")
    op = str(rep.get("supplier_oper_name", "") or "")
    penalty = float(rep.get("penalty", 0) or 0)

    if op == "Штраф" and penalty != 0:
        tot["total_penalty_raw"] += penalty
        if not sa.strip() or sa == "0":
            sa = "БЕЗ_АРТИКУЛА"
            tot["unassigned_penalty"] += penalty
        else:
            tot["assigned_penalty"] += penalty
        if not size.strip() or size == "0":
            size = "БЕЗ_РАЗМЕРА"

    if not sa.strip():
        sa = "БЕЗ_АРТИКУЛА"
    if not size.strip():
        size = "БЕЗ_РАЗМЕРА"

    key = (sa, size)
    row = rows.get(key)
    if row is None:
        row = AggregatedRow(
            client=rep.get("supplier_name", ""),
            article_seller=sa if sa != "БЕЗ_АРТИКУЛА" else "",
            predmet=rep.get("subject_name", "") or ("Штраф" if op == "Штраф" else ""),
            size=size if size != "БЕЗ_РАЗМЕРА" else "",
            article_wb=str(rep.get("nm_id", "0")),
        )
        rows[key] = row

    doc = str(rep.get("doc_type_name", "") or "").lower()
    bonus_type = str(rep.get("bonus_type_name", "") or "")

    qty = float(rep.get("quantity", 0) or 0)
    retail_amount = float(rep.get("retail_amount", 0) or 0)
    retail_price_withdisc_rub = float(rep.get("retail_price_withdisc_rub", 0) or 0)
    cashback_discount = float(rep.get("cashback_discount", 0) or 0)
    cashback_commission_change = float(rep.get("cashback_commission_change", 0) or 0)
    cashback_amount = float(rep.get("cashback_amount", 0) or 0)
    ppvz_for_pay = float(rep.get("ppvz_for_pay", 0) or 0)
    delivery_rub = float(rep.get("delivery_rub", 0) or 0)
    penalty = float(rep.get("penalty", 0) or 0)
    deduction = float(rep.get("deduction", 0) or 0)
    storage_fee = float(rep.get("storage_fee", 0) or 0)
    acceptance = float(rep.get("acceptance", 0) or 0)
    rebill_logistic_cost = float(rep.get("rebill_logistic_cost", 0) or 0)
    commission_percent = float(rep.get("commission_percent", 0) or 0)

    if op == "Продажа":
        row.summ_sales += retail_amount
        row.delivery_amount += qty
        tot["total_sales"] += retail_amount
        tot["total_qty_sales"] += qty

    if op == "Возврат":
        row.summ_returns += retail_amount
        row.return_amount += qty
        tot["total_returns"] += retail_amount

    row.retail_price_withdisc_rub += retail_price_withdisc_rub
    row.cashback_discount += cashback_discount
    row.cashback_commission_change += cashback_commission_change

    if doc == "продажа" and op == "Продажа":
        row.sales += ppvz_for_pay
    if doc == "продажа" and op == "Добровольная компенсация при возврате":
        row.goods_return += ppvz_for_pay
    if op == "Компенсация ущерба":
        if doc == "продажа":
            row.kompensation += ppvz_for_pay
        elif doc == "возврат":
            row.kompensation_returns += ppvz_for_pay
    if op in ("Компенсация подмененного товара", "Компенсация потерянного товара"):
        row.kompensation += ppvz_for_pay
    if op == "Коррекция продаж":
        if doc == "продажа":
            row.korrect_sales += ppvz_for_pay
        elif doc == "возврат":
            row.korrect_sales_returns += ppvz_for_pay
    if doc == "возврат" and op == "Возврат":
        row.returns += ppvz_for_pay
    if op == "Корректировка эквайринга":
        row.equaring += ppvz_for_pay
    if op == "Логистика":
        if doc == "возврат":
            row.logistics_returns += delivery_rub
        else:
            row.logistics += delivery_rub
    if op in ("Логистика сторно", "Сторно логистики"):
        row.storno_logistics += delivery_rub
    if op == "Сторно возвратов":
        row.storno_returns += ppvz_for_pay
    if op == "Коррекция логистики":
        row.correction_logistics += delivery_rub
    if op == "Возмещение издержек по перевозке/по складским операциям с товаром":
        row.kompensation_logistics += rebill_logistic_cost
    if op == "Штраф":
        row.penalty += penalty
        tot["penalty"] += penalty
    if op.lower() in ("удержание", "удержания"):
        if bonus_type in (
            "Оказание услуг «WB Продвижение»",
            "Оказание услуг «ВБ.Продвижение»",
        ):
            tot["internal_ad_total"] += deduction
        elif bonus_type == "Перевод на баланс заёмщика":
            tot["credit_payment_total"] += deduction
        elif bonus_type == "Предоставление услуг по подписке «Джем»":
            tot["jem_total"] += deduction
        else:
            row.deduction += deduction
            tot["deduction_raw"] += deduction
    if storage_fee:
        row.storage_fee += storage_fee
        tot["storage_fee"] += storage_fee
    if op == "Платная приемка":
        row.acceptance += acceptance
        tot["acceptance"] += acceptance
    if op in ("Пересчет платной приемки", "Корректировка приемки"):
        row.kompensation_priemki += acceptance
        tot["kompensation_priemki"] += acceptance
    if doc == "возврат" and op == "Добровольная компенсация при возврате":
        row.goods_return_return += ppvz_for_pay
        tot["goods_return_return"] += ppvz_for_pay
    if op == "Возмещение за выдачу и возврат товаров на ПВЗ":
        row.pvz_compensation += ppvz_for_pay
        tot["pvz_compensation"] += ppvz_for_pay
    if op == "Компенсация скидки по программе лояльности":
        row.loyalty_discount_compensation += ppvz_for_pay
        tot["loyalty_discount_compensation"] += ppvz_for_pay
    if op == "Обработка товара":
        row.goods_processing += acceptance
        tot["goods_processing"] += acceptance
    if op == "Стоимость участия в программе лояльности":
        row.loyalty_program_cost += cashback_commission_change
        tot["loyalty_program_cost"] += cashback_commission_change
    if op == "Сумма удержанная за начисленные баллы программы лояльности":
        row.loyalty_points_deduction += cashback_amount
        tot["loyalty_points_deduction"] += cashback_amount
    if commission_percent != 0:
        row.commission_percent = commission_percent


def aggregate_rows_streaming(
    pages_iterator: Iterator[list[dict[str, Any]]],
) -> tuple[list[AggregatedRow], dict[str, float]]:
    """Aggregate WB report data incrementally from a page iterator."""
    rows: dict[tuple[str, str], AggregatedRow] = {}
    tot: defaultdict[str, float] = defaultdict(float)

    for page in pages_iterator:
        for rep in page:
            _process_single_row(rep, rows, tot)

    tot["deduction"] = tot.get("deduction_raw", 0.0)

    totals = {
        "storage_fee": tot.get("storage_fee", 0.0),
        "deduction": tot.get("deduction", 0.0),
        "penalty": tot.get("penalty", 0.0),
        "acceptance": tot.get("acceptance", 0.0),
        "kompensation_priemki": tot.get("kompensation_priemki", 0.0),
        "penalty_total": tot.get("penalty", 0.0),
        "internal_ad_total": tot.get("internal_ad_total", 0.0),
        "credit_payment_total": tot.get("credit_payment_total", 0.0),
        "jem_total": tot.get("jem_total", 0.0),
        "pvz_compensation": tot.get("pvz_compensation", 0.0),
        "loyalty_discount_compensation": tot.get("loyalty_discount_compensation", 0.0),
        "goods_processing": tot.get("goods_processing", 0.0),
        "loyalty_program_cost": tot.get("loyalty_program_cost", 0.0),
        "loyalty_points_deduction": tot.get("loyalty_points_deduction", 0.0),
    }

    return list(rows.values()), totals

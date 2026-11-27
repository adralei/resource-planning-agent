
"""Safely retry dated-plan application after confirming persisted state."""

from resource_planning_agent.planning.dated_application_confirmation import (
    confirm_dated_plan_application,
)
from resource_planning_agent.planning.dated_plan_application import (
    apply_approved_dated_plan,
)


def _validate_confirmation(result, plan_id):
    """
    Confirmation servisinin donus sozlesmesini
    dogrular. Bilinmeyen veya celiskili sonuclari
    basarili kabul etmez.
    """

    if not isinstance(result, dict):
        raise ValueError("Confirmation sonucu gecersiz.")

    if result.get("plan_id") != plan_id:
        raise ValueError(
            "Confirmation plan kimligi uyusmuyor."
        )

    status = result.get("status")

    if status == "confirmed_applied":
        if (
            result.get("confirmed") is not True
            or result.get("safe_to_retry") is not False
            or type(result.get("reservation_count")) is not int
            or result["reservation_count"] <= 0
        ):
            raise ValueError(
                "Confirmed application sonucu celiskili."
            )

        return status

    if status == "not_applied":
        if (
            result.get("confirmed") is not False
            or result.get("safe_to_retry") is not True
            or result.get("reservation_count") != 0
        ):
            raise ValueError(
                "Not-applied sonucu celiskili."
            )

        return status

    raise ValueError(
        "Bilinmeyen application confirmation durumu."
    )


def _confirmed_result(confirmation, outcome):
    """
    Dogrulanmis uygulama kaydindan sonuc uretir.
    """

    return {
        "status": "confirmed_applied",
        "plan_id": confirmation["plan_id"],
        "outcome": outcome,
        "confirmed": True,
        "reservation_count": confirmation[
            "reservation_count"
        ],
        "approval_fingerprint": confirmation.get(
            "approval_fingerprint"
        ),
        "applied_at": confirmation.get("applied_at"),
    }


def apply_dated_plan_safely(plan_id):
    """
    Tarihli planin guvenli yeniden deneme akisi.

    1. Mevcut uygulama sonucunu dogrular.
    2. Zaten uygulanmissa tekrar rezervasyon yapmaz.
    3. Uygulanmamissa normal uygulama servisini cagirir.
    4. Islemden sonra SQLite sonucunu tekrar dogrular.
    5. Uygulama hata verse bile commit gerceklesmisse
       dogrulanmis basariyi raporlayabilir.

    Yeni onay olusturmaz.
    Eksik registry kaydini onarmaz.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    initial = confirm_dated_plan_application(plan_id)

    status = _validate_confirmation(
        initial,
        plan_id,
    )

    if status == "confirmed_applied":
        return _confirmed_result(
            initial,
            "already_applied",
        )

    try:
        apply_approved_dated_plan(plan_id)

    except Exception:
        # Hata, COMMIT sonrasinda olusmus olabilir.
        # Yeni bir uygulama denemeden once kayitlari
        # yeniden dogrula.
        after_error = confirm_dated_plan_application(
            plan_id
        )

        after_status = _validate_confirmation(
            after_error,
            plan_id,
        )

        if after_status == "confirmed_applied":
            return _confirmed_result(
                after_error,
                "confirmed_after_error",
            )

        # Islem uygulanmamis: asil uygulama hatasini
        # cagirana yeniden ilet.
        raise

    # Servisin basarili donmesi tek basina yeterli
    # degil; kalici kayitlari da kontrol ediyoruz.
    final = confirm_dated_plan_application(plan_id)

    final_status = _validate_confirmation(
        final,
        plan_id,
    )

    if final_status != "confirmed_applied":
        raise RuntimeError(
            "Uygulama servisi dondu ancak kalici "
            "uygulama kaydi dogrulanamadi."
        )

    return _confirmed_result(
        final,
        "newly_applied",
    )

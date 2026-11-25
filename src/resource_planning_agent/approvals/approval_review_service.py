
import sqlite3

from resource_planning_agent.approvals.approval_review_case import (
    prepare_approval_review_case,
)

from resource_planning_agent.storage.approval_review_store import (
    initialize_review_case_store,
    save_approval_review_case,
    get_open_review_case_for_plan,
)


def open_approval_review_case(plan_id):
    """
    Tutarsiz plan icin inceleme vakasi acar.

    Ayni planin ayni tutarsizlik icin acik vakasi
    varsa onu tekrar kullanir.

    Plan, onay veya rezervasyon kayitlarini
    degistirmez.
    """

    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("Gecerli plan_id gerekli.")

    # Her istekte mevcut tutarsizligi yeniden kontrol et.
    review_case = prepare_approval_review_case(plan_id)

    initialize_review_case_store()

    def check_existing(existing):
        if existing is None:
            return None

        if (
            existing.get("plan_id") != plan_id
            or existing.get("case_status") !=
                "awaiting_manual_review"
        ):
            raise ValueError(
                "Mevcut inceleme vakasi gecersiz."
            )

        if (
            existing.get("consistency_status")
            != review_case["consistency_status"]
        ):
            raise ValueError(
                "Planin tutarsizlik durumu degismis. "
                "Mevcut vaka manuel incelenmeli."
            )

        return {
            "created": False,
            "case": existing,
        }

    existing = get_open_review_case_for_plan(plan_id)

    result = check_existing(existing)

    if result is not None:
        return result

    try:
        save_approval_review_case(review_case)

    except sqlite3.IntegrityError:
        # Eszamanli baska bir istek vaka olusturmus
        # olabilir. Yalnizca mevcut kayit bulunursa
        # tekrar kullan; diger hatalari gizleme.
        existing = get_open_review_case_for_plan(plan_id)

        result = check_existing(existing)

        if result is not None:
            return result

        raise

    return {
        "created": True,
        "case": review_case,
    }

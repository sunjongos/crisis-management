import math

NDB_PROFILE = {
    "operating_beds": 102,
    "daily_rev_eok": 1.03,
    "monthly_fixed_cost_eok": 20.60,
    "daily_fixed_cost_eok": 0.675,
    "variable_cost_rate": 0.205,
    "non_op_net_eok": 0.10,
    "bep_monthly_rev_eok": 25.91,
    "actual_cash_reserve_eok": 96.5,
    "bucket1_safety_cash_eok": 55.0,
    "dec_seasonal_surge_pct": 21.3,
}

def evaluate_management_crisis(
    beds: int,
    weekend_dis: int = 25,
    planned_adm: int = 8,
    day_ward: int = 0,
    proj_rev_eok: float = 27.80,
    reported_cash_eok: float | None = None,
    cash_basis: str = "BANK_ACTUAL",  # "BANK_ACTUAL" | "YTD_NET_CF" | "UNKNOWN"
    early_discharge_cnt: int = 0,
):
    p = NDB_PROFILE
    mon_beds = max(0, int(round(beds + planned_adm + 0.5 * day_ward - weekend_dis - early_discharge_cnt)))
    eff_min_beds = min(beds, mon_beds)
    cm_rate = 1.0 - p["variable_cost_rate"]
    op_profit = proj_rev_eok * cm_rate - p["monthly_fixed_cost_eok"]
    ebt = op_profit + p["non_op_net_eok"]
    opm = op_profit / proj_rev_eok if proj_rev_eok > 0.01 else -1.0
    t6_leverage = round(1.0 / max(0.01, opm), 1) if opm > 0 else 50.0

    kill_switches, notes = [], []
    real_cash = p["actual_cash_reserve_eok"]
    if reported_cash_eok is not None:
        if cash_basis == "YTD_NET_CF":
            notes.append(f"[AX-02 현금착시 기각] {reported_cash_eok}억(누적수지차) 기각 -> 실보유현금 {real_cash}억 적용")
        elif cash_basis == "BANK_ACTUAL":
            real_cash = reported_cash_eok
            if real_cash < p["bucket1_safety_cash_eok"]:
                kill_switches.append("D-T5_TRUE_BANK_CASH_BELOW_55EOK")

    if early_discharge_cnt > 0:
        daily_bed_rev = (p["daily_rev_eok"] * 0.70) / 73.0
        imm_gain = early_discharge_cnt * 3.2 * daily_bed_rev
        next_loss = early_discharge_cnt * 5.5 * daily_bed_rev * (1 + p["dec_seasonal_surge_pct"] / 100.0)
        if (imm_gain - next_loss) < 0 or (beds - early_discharge_cnt) < 60:
            kill_switches.append(f"AX-03_CANNIBALIZATION_REJECT (2M_Net_EV={imm_gain - next_loss:.2f}억)")

    if "D-T5_TRUE_BANK_CASH_BELOW_55EOK" in kill_switches:
        stage = "D-T5 (유동성 마지노선 침범 비상)"
    elif eff_min_beds < 50 or proj_rev_eok <= p["bep_monthly_rev_eok"] + 0.6:
        stage = "M-T4 (경영 4단계 중대 · 선발주 동결 & 중간수납)"
    elif eff_min_beds < 60 or proj_rev_eok < 28.5:
        stage = "M-T3 (경영 3단계 심각 · 비상입원 & IS 병목타격)"
    elif eff_min_beds < 68 or weekend_dis >= 25:
        stage = "M-T2 (경영 2단계 경계 · 목요일 계획입원 & 낮병동)"
    elif eff_min_beds < 75:
        stage = "M-T1 (경영 1단계 주의)"
    else:
        stage = "NORMAL (정상 순항)"

    basket = "NO" if kill_switches else ("TOO TOUGH" if cash_basis == "UNKNOWN" else "YES")
    return {
        "stage": stage,
        "munger_basket": basket,
        "friday_beds": beds,
        "projected_monday_beds": mon_beds,
        "admission_deficit_to_68": max(0, 68 - mon_beds),
        "estimated_ebt_eok": round(ebt, 2),
        "t6_cost_leverage": t6_leverage,
        "verified_cash_eok": real_cash,
        "december_backcast_target_eok": round(proj_rev_eok * 1.213, 2),
        "kill_switches": kill_switches,
        "notes": notes,
    }

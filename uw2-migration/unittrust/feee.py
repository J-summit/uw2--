import sys
def calc(amount, charge):
    c = charge / 100
    total_charge = amount - (amount / (1 + c + c * 0.08))
    sst_total_charge = total_charge - ((c / (c + c * 0.08)) * total_charge)
    return total_charge, sst_total_charge

if __name__ == "__main__":
    amount = 1000.00
    charge = 3
    t, s = calc(amount, charge)
    print(f"total_charge={t:.6f}")
    print(f"sst_total_charge={s:.6f}")
int control(int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        if (i % 2 == 0) {
            total += i;
        } else if (i == 7) {
            continue;
        } else {
            total -= i;
        }
    }
    while (total > 100) {
        total = total / 2;
        if (total < 0) break;
    }
    return total;
}

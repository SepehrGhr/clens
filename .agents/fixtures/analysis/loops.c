/* CFG loop shapes: back-edges, break, continue, nested loops, and an
   infinite loop whose EXIT is genuinely unreachable (correct, not a bug). */
int loops(int n) {
    int total = 0;
    while (n > 0) {
        if (n == 3) { n = n - 1; continue; }
        if (n == 7) { break; }
        for (int i = 0; i < n; i++) {
            total = total + i;
        }
        n = n - 1;
    }
    return total;
}

int spin(void) {
    while (1) {
        int x = 0;
        x = x + 1;
    }
}

/* Every call-graph query in one file (A3.5).
   - self_recursive: direct recursion, single-node SCC WITH a self-edge
   - ping/pong: mutual recursion, 2-node SCC
   - a/b/c: 3-cycle SCC
   - orphan: dead function, unreachable from main
   - only_from_orphan: reachable only via a dead function, also dead
   - leaf: called, calls nothing, single-node SCC WITHOUT a self-edge */
int leaf(int n) { return n + 1; }

int self_recursive(int n) {
    if (n <= 0) return 0;
    return self_recursive(n - 1);
}

int pong(int n);
int ping(int n) { if (n <= 0) return 0; return pong(n - 1); }
int pong(int n) { if (n <= 0) return 0; return ping(n - 1); }

int c_fn(int n);
int a_fn(int n) { return c_fn(n); }
int b_fn(int n) { return a_fn(n); }
int c_fn(int n) { return b_fn(n); }

int only_from_orphan(void) { return 1; }
int orphan(void) { return only_from_orphan(); }

int main(void) {
    int r = leaf(1);
    r = r + self_recursive(3);
    r = r + ping(4);
    r = r + a_fn(5);
    return r;
}

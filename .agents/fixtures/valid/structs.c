/* struct + member access. In scope: Phase 2 completion depends on it. */
struct Point {
    int x;
    int y;
};

int sum(struct Point *p) {
    struct Point local;
    local.x = 1;
    local.y = 2;
    return p->x + p->y + local.x + local.y;
}

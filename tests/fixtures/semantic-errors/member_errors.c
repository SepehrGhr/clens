/* Swapped member operators and unknown fields. */
struct Point { int x; int y; };

int f(void) {
    struct Point p;
    struct Point *q;
    int a = p->x;      /* arrow on non-pointer: did you mean '.'? */
    int b = q.y;       /* dot on pointer: did you mean '->'? */
    int c = p.z;       /* unknown field 'z' in struct Point */
    return a + b + c;
}

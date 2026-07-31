/* S5.6 golden completion fixture.
   NOTE: the course document writes `struct Point p = {1, 2};` but initializer
   lists are out of subset (03-c-subset.md), so this uses a plain declaration.
   Recorded in docs/known-limitations.md. Completion at the '.' must offer
   exactly x : int and y : int. */
struct Point {
    int x;
    int y;
};

int use(void) {
    struct Point p;
    struct Point *q;
    p.x = 1;
    q->y = 2;
    return p.x + q->y;
}

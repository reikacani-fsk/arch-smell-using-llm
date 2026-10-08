package com.ex.a;

import com.ex.b.Beta;

/** Alpha depends on Beta. */
public class Alpha {
    private Beta beta = new Beta();
    public int value() { return beta.compute() + 1; }
}

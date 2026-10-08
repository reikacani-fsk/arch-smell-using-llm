using System;
using Ex.B;

namespace Ex.A;

/// <summary>Alpha depends on Beta.</summary>
public class Alpha
{
    private Beta beta = new Beta();
    public int Value() { return beta.Compute() + 1; }
}

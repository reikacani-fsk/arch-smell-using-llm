namespace Ex.D
{
    public class Delta
    {
        public const int Limit = 3;
        public enum Mode { Fast, Slow }
        class Inner { void Hidden() { System.Console.WriteLine("x"); } }
        public Delta() { }
        public string Name(int i) { return "d" + i; }
        public int Size { get; private set; }
#if DEBUG
        private int dbg;
#endif
    }
}

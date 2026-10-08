using Ex.B;

namespace Ex.C
{
    public class Gamma
    {
        public object Beta { get; set; }   // a member named like a type is not a reference

        public int Run()
        {
            // long body that must disappear in the skeleton
            var x = new Ex.A.Alpha().Value();
            return x * 2 + (this.Beta == null ? 0 : 1);
        }
    }
}

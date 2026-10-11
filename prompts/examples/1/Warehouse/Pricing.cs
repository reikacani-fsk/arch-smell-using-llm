using Warehouse.Data;

namespace Warehouse.Pricing;

public class PriceList
{
    private readonly Database _db = new();

    public decimal PriceOf(string sku) => decimal.Parse(_db.Read($"price:{sku}") ?? "0");

    public void SetPrice(string sku, decimal price) => _db.Write($"price:{sku}", price.ToString());
}

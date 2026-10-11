using Shop.Core.Common;
using Shop.Core.Orders;

namespace Shop.Core.Billing;

public class Invoice
{
    public Order Order { get; init; } = null!;
    public decimal Amount { get; init; }
}

public class InvoiceService
{
    private readonly List<Invoice> _issued = new();

    public Invoice CreateFor(Order order)
    {
        var invoice = new Invoice { Order = order, Amount = order.Total };
        _issued.Add(invoice);
        return invoice;
    }

    public string Export() =>
        new CsvExporter(new CsvOptions(';')).Write(_issued.Select(i => new[] { i.Order.Id.ToString(), i.Amount.ToString() }));
}

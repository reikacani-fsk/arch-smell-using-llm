using Shop.Core.Billing;
using Shop.Core.Common;
using Shop.Core.Customers;

namespace Shop.Core.Orders;

public class Order
{
    public int Id { get; init; }
    public Customer Customer { get; init; } = null!;
    public List<decimal> Lines { get; } = new();
    public decimal Total => Lines.Sum();
}

public class OrderService
{
    private readonly InvoiceService _invoices = new();
    private readonly EmailSender _email = new(new SmtpSettings("smtp.shop.local", 25));

    public Invoice Checkout(Order order)
    {
        var invoice = _invoices.CreateFor(order);
        _email.Send(order.Customer.Email, $"Order {order.Id} confirmed");
        return invoice;
    }
}

# How the architectural smells of rkacani/bookstore emerged

## 1. Dense Structure in <All namespaces included> (<All projects included>)

**Designite:** The tool detected the smell because all the analyzed components exhibit excessive and dense dependencies among themselves. Average degree = 5'56  All the dependencies among components: from: Bookstore.Admin' to: Bookstore.Catalog' from: Bookstore.Admin' to: Bookstore.Customers' from: Bookstore.Admin' to: Bookstore.Billing' from: Bookstore.Admin' to: Bookstore.Notifications' from: Bookstore.Admin' to: Bookstore.Orders' from: Bookstore.Admin' to: Bookstore.Shipping' from: Bookstore.Billing' to: Bookstore.Orders' from: Bookstore.Customers' to: Bookstore.Notifications' from: Bookstore.Integration' to: Bookstore.Orders' from: Bookstore.Notifications' to: Bookstore.Catalog' from: Bookstore.Orders' to: Bookstore.Catalog' from: Bookstore.Orders' to: Bookstore.Customers' from: Bookstore.Orders' to: Bookstore.Billing' from: Bookstore.Orders' to: Bookstore.Notifications' from: Bookstore.Reporting' to: Bookstore.Admin' from: Bookstore.Reporting' to: Bookstore.Catalog' from: Bookstore.Reporting' to: Bookstore.Customers' from: Bookstore.Reporting' to: Bookstore.Notifications' from: Bookstore.Reporting' to: Bookstore.Orders' from: Bookstore.Reporting' to: Bookstore.Integration' from: Bookstore.Reporting' to: Bookstore.Billing' from: Bookstore.Reporting' to: Bookstore.Shipping' from: Bookstore.Shipping' to: Bookstore.Customers' from: Bookstore.Shipping' to: Bookstore.Orders' from: Bookstore.Shipping' to: Bookstore.Notifications.

**Classes:** Bookstore.Admin.AddBookCommand; Bookstore.Admin.RemoveBookCommand; Bookstore.Admin.RenameBookCommand; Bookstore.Admin.ChangeAuthorCommand; Bookstore.Admin.ChangePriceCommand; Bookstore.Admin.ShowBookCommand; Bookstore.Admin.ListBooksCommand; Bookstore.Admin.CountBooksCommand; Bookstore.Admin.AddCustomerCommand; Bookstore.Admin.RemoveCustomerCommand; Bookstore.Admin.ChangeEmailCommand; Bookstore.Admin.ChangeAddressCommand; Bookstore.Admin.AddLoyaltyPointsCommand; Bookstore.Admin.ShowCustomerCommand; Bookstore.Admin.ListCustomersCommand; Bookstore.Admin.ListInvoicesCommand; Bookstore.Admin.ShowInvoiceCommand; Bookstore.Admin.CountInvoicesCommand; Bookstore.Admin.SendNewsletterCommand; Bookstore.Admin.PreviewNewsletterCommand; Bookstore.Admin.ShowOutboxCommand; Bookstore.Admin.ListOrdersCommand; Bookstore.Admin.ShowOrderCommand; Bookstore.Admin.CancelOrderCommand; Bookstore.Admin.ReopenOrderCommand; Bookstore.Admin.CountOrdersCommand; Bookstore.Admin.ShipOrderCommand; Bookstore.Admin.TrackShipmentCommand; Bookstore.Admin.ListShipmentsCommand; Bookstore.Admin.CountShipmentsCommand; Bookstore.Billing.PaymentService; Bookstore.Customers.CustomerService; Bookstore.Integration.PartnerApi; Bookstore.Notifications.RecommendationBlock; Bookstore.Orders.CartService; Bookstore.Orders.CheckoutService; Bookstore.Orders.OrderConfirmation; Bookstore.Orders.OrderService; Bookstore.Reporting.AdminReport; Bookstore.Reporting.CatalogReport; Bookstore.Reporting.CustomerReport; Bookstore.Reporting.EmailReport; Bookstore.Reporting.OrderReport; Bookstore.Reporting.PartnerReport; Bookstore.Reporting.RevenueReport; Bookstore.Reporting.ShipmentReport; Bookstore.Shipping.AddressLookup; Bookstore.Shipping.ShipmentService; Bookstore.Shipping.ShippingNotifier

**Commits that changed its files:** 19

**Emerged in:** 3c965910f7 2025-04-12

**How:** I traced the namespace edges from the `using Bookstore.*` directives at each commit. The graph grew step by step. c234c7eee4 (shipping) brought in Orders->Billing, Orders->Catalog, Shipping->Customers and Shipping->Orders. a86bbbb882 added Billing->Orders through InvoiceService listing order lines. ca5b8bd971 (emails) added Customers->Notifications, Orders->Notifications and Shipping->Notifications. 4143cc872d (admin console) added Admin->Catalog and Admin->Customers. e2f30f57f6 added Integration->Orders. 1839acf54d (loyalty pricing) added Orders->Customers. 10a633cd5d added Notifications->Catalog. bfc2573685 added Admin->Notifications and Admin->Orders. 45ae161a74 briefly removed Billing->Orders by passing order data to billing as plain values. ce7435fa0a added Admin->Billing and Admin->Shipping. b117c1ad36 brought Billing->Orders back through PaymentService.Settle, which looks up and updates the Order. 146ae038ea's CartService repeated edges that already existed. At 3c965910f7~1 there were 17 distinct edges among 8 namespaces, an average degree of 4.25, which is below the density threshold. The edge count never went higher before that, so the smell was never present earlier. 3c965910f7 ('Add management dashboard') added the Reporting namespace with eight per-area report classes (CatalogReport, CustomerReport, OrderReport, RevenueReport, ShipmentReport, EmailReport, PartnerReport, AdminReport). Each one depends on a different namespace, which added 8 edges and a 9th component: 25 edges over 9 components gives the reported average degree of 5.56. The analyzed commit 9a6634f70f only changed method bodies in InvoiceService, PaymentService and OrderService and added no edges, so the smell is unchanged.

**Timeline:**

- `c234c7eee4`: Shipping added. Edges at this commit: Orders->Billing, Orders->Catalog, Shipping->Customers, Shipping->Orders.
- `a86bbbb882`: InvoiceService uses Orders to list order lines, adding Billing->Orders.
- `ca5b8bd971`: Welcome, order and shipping emails add Customers/Orders/Shipping -> Notifications.
- `4143cc872d`: Admin console adds Admin->Catalog and Admin->Customers.
- `e2f30f57f6`: PartnerApi adds Integration->Orders.
- `1839acf54d`: Loyalty discount pricing adds Orders->Customers.
- `10a633cd5d`: RecommendationBlock adds Notifications->Catalog.
- `bfc2573685`: Admin order and newsletter commands add Admin->Orders and Admin->Notifications.
- `45ae161a74`: Billing->Orders is temporarily removed by passing plain values.
- `ce7435fa0a`: Admin shipment and invoice commands add Admin->Shipping and Admin->Billing, so Admin now depends on 6 namespaces.
- `b117c1ad36`: PaymentService brings Billing->Orders back, a two-way link with Orders->Billing (17 edges among 8 namespaces).
- `3c965910f7`: Reporting namespace with 8 report classes adds 8 outgoing edges, one to every other namespace (25 edges over 9 components, average degree 5.56), and the smell appears.

**Why it is a problem:** 

## 2. God Component in Bookstore.Admin (Bookstore)

**Designite:** The tool detected the smell in this component because the component contains high number of classes. Number of classes in the component are: 32

**Classes:** Bookstore.Admin.AdminCommand; Bookstore.Admin.AdminConsole; Bookstore.Admin.AddBookCommand; Bookstore.Admin.RemoveBookCommand; Bookstore.Admin.RenameBookCommand; Bookstore.Admin.ChangeAuthorCommand; Bookstore.Admin.ChangePriceCommand; Bookstore.Admin.ShowBookCommand; Bookstore.Admin.ListBooksCommand; Bookstore.Admin.CountBooksCommand; Bookstore.Admin.AddCustomerCommand; Bookstore.Admin.RemoveCustomerCommand; Bookstore.Admin.ChangeEmailCommand; Bookstore.Admin.ChangeAddressCommand; Bookstore.Admin.AddLoyaltyPointsCommand; Bookstore.Admin.ShowCustomerCommand; Bookstore.Admin.ListCustomersCommand; Bookstore.Admin.ListInvoicesCommand; Bookstore.Admin.ShowInvoiceCommand; Bookstore.Admin.CountInvoicesCommand; Bookstore.Admin.SendNewsletterCommand; Bookstore.Admin.PreviewNewsletterCommand; Bookstore.Admin.ShowOutboxCommand; Bookstore.Admin.ListOrdersCommand; Bookstore.Admin.ShowOrderCommand; Bookstore.Admin.CancelOrderCommand; Bookstore.Admin.ReopenOrderCommand; Bookstore.Admin.CountOrdersCommand; Bookstore.Admin.ShipOrderCommand; Bookstore.Admin.TrackShipmentCommand; Bookstore.Admin.ListShipmentsCommand; Bookstore.Admin.CountShipmentsCommand

**Commits that changed its files:** 3

**Emerged in:** ce7435fa0a 2025-04-04

**How:** 4143cc872d created Bookstore.Admin with the AdminCommand base class, AdminConsole and one class per command for the catalog (8 commands) and customers (7 commands), 17 classes in total. bfc2573685 added OrderCommands.cs (5 commands) and NewsletterCommands.cs (3 commands), which brought it to 25 classes. ce7435fa0a added ShippingCommands.cs (4 commands) and InvoiceCommands.cs (3 commands), which brought it to 32 classes. That is over the class-count threshold, so the smell appears in this commit; at its parent the component had 25 classes. No later commit touched src/Bookstore/Admin, so the smell is still present at 9a6634f70f.

**Timeline:**

- `4143cc872d`: Admin component created with AdminCommand, AdminConsole and 15 catalog/customer command classes (17 classes)
- `bfc2573685`: Added 5 order commands and 3 newsletter commands (25 classes)
- `ce7435fa0a`: Added 4 shipping commands and 3 invoice commands (32 classes); the threshold is crossed

**Why it is a problem:** Bookstore.Admin keeps one command class for every operation of every other module: Catalog, Customers, Orders, Billing, Notifications and Shipping. It therefore depends on almost the whole system, and any feature change anywhere also means changing Admin. Admin commands for each module could not be owned, tested or reused separately, and the component keeps growing with each new feature.

## 3. Cyclic Dependency in Bookstore.Billing (Bookstore)

**Designite:** The tool detected the smell in this component because this component participates in a cyclic dependency. The participating components in the cycle are: Bookstore.Billing' Bookstore.Orders

**Classes:** Bookstore.Billing.PaymentService; Bookstore.Orders.CartService; Bookstore.Orders.CheckoutService; Bookstore.Orders.OrderConfirmation

**Commits that changed its files:** 7

**Emerged in:** b117c1ad36 2025-04-10

**How:** eaa567433e added Orders.CheckoutService, which depends on Billing.InvoiceService and Invoice (Orders -> Billing). At first, Billing only took plain values. a86bbbb882 changed InvoiceService.CreateFor to take an Order and read its OrderLines and OrderStatus ('using Bookstore.Orders'). That created a first Billing <-> Orders cycle. 45ae161a74 ('Pass order data to billing as plain values') removed the cycle: CreateFor went back to (orderId, amount, lines) and the Orders import was dropped, so from 45ae161a74 through 146ae038ea Billing did not depend on Orders. b117c1ad36 added Billing.PaymentService, which uses OrderRepository, Order, OrderLine and OrderStatus to mark orders as paid. That brought back Billing -> Orders while CheckoutService still had Orders -> Billing, so the cycle came back. 9a6634f70f only added a check inside PaymentService.Settle (return early if the invoice is already paid) and kept the cycle.

**Timeline:**

- `eaa567433e`: CheckoutService (Orders) starts calling Billing.InvoiceService: Orders -> Billing
- `a86bbbb882`: InvoiceService.CreateFor takes an Order and walks its OrderLines: Billing -> Orders; the first cycle appears
- `45ae161a74`: Billing gets plain values instead of Order; the cycle is removed
- `b117c1ad36`: PaymentService added in Billing; it reads and updates Orders' OrderRepository/Order/OrderStatus, so the cycle comes back
- `9a6634f70f`: PaymentService.Settle tidied up; the dependency on Orders remains

**Why it is a problem:** Checkout in Orders creates invoices, and payment in Billing reaches back into OrderRepository and sets Order.Status, so neither module can be built, tested or changed without the other. The team had already broken this cycle once in 45ae161a74 by passing plain values. PaymentService brings back the same coupling, so a change to Order or OrderLine (for example, how totals are computed) now affects Billing's payment logic as well.

## 4. Unstable Dependency in Bookstore.Customers (Bookstore)

**Designite:** The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): Bookstore.Notifications

**Classes:** Bookstore.Customers.EmailSender

**Commits that changed its files:** 2

**Emerged in:** 10a633cd5d 2025-03-27

**How:** ca5b8bd971 added the Notifications component (EmailSender, EmailTemplate). In the same commit Customers.CustomerService started using EmailSender to send welcome mails, so Customers -> Notifications. At that point Notifications had no outgoing dependencies (instability 0), so the dependency was not unstable. 10a633cd5d ('Recommend books at the end of every email') added RecommendationBlock, which uses Bookstore.Catalog, and attached it to EmailSender. Notifications then had efferent coupling and could become less stable than Customers. Customers is used by many classes (Admin customer commands, OrderService, CartService, Shipping.AddressLookup and later reporting) and depends only on Notifications. Notifications also gained dependents afterwards (Admin newsletter commands in bfc2573685, EmailReport in 3c965910f7). How the tool weights the coupling is not visible: if you count only namespaces, Notifications does not come out less stable. What the history does show is that the smell could not exist before 10a633cd5d, because Notifications had instability 0 until then.

**Timeline:**

- `ca5b8bd971`: Notifications introduced; CustomerService depends on EmailSender (Customers -> Notifications)
- `10a633cd5d`: EmailSender gets a RecommendationBlock that depends on Catalog, so Notifications becomes unstable

**Why it is a problem:** Customers is a core module that orders, shipping and admin depend on. Through CustomerService it is tied to EmailSender, whose behaviour keeps changing, for example the catalog-based recommendation footer. Changes to email layout or recommendations can therefore ripple into customer registration and into everything that depends on Customers.

## 5. Ambiguous Interface in Bookstore.Integration (Bookstore)

**Designite:** The tool detected the smell in this component because the component provides only a single' general entry-point via the following class: PartnerApi

**Classes:** Bookstore.Integration.PartnerApi

**Commits that changed its files:** 2

**Emerged in:** a62b06d0cf 2025-04-02

**How:** e2f30f57f6 added Bookstore.Integration with PartnerApi exposing three typed public methods: ExportOrders(), ImportOrder(PartnerOrder) and CancelOrder(int). a62b06d0cf ('Route all partner calls through one Handle entry point') made these methods private. It added a single public Handle(string command, object payload), which switches on strings like "export-orders", "import-order" and "cancel-order" and casts the payload. Since then, PartnerApi's only public members are its constructor and Handle. No later commit changed the Integration folder.

**Timeline:**

- `e2f30f57f6`: PartnerApi added with three explicit, typed public operations
- `a62b06d0cf`: Operations made private behind a single Handle(string, object) dispatcher

**Why it is a problem:** Callers of the partner integration can no longer see from the interface that it exports, imports and cancels orders, or which payload type each command needs. A wrong command string or a payload of the wrong type (PartnerOrder vs int) only fails at runtime through a cast or the 'unknown-command' branch. The compiler no longer checks the contract, and the dependencies of each operation are hidden.

## 6. Scattered Functionality in Bookstore.Orders (Bookstore)

**Designite:** The tool detected the smell in this component because a set of two or more components realizes the same high-level architectural concern. Following components realize the same concern: Bookstore.Catalog' Bookstore.Customers

**Classes:** Bookstore.Catalog.PriceList; Bookstore.Customers.LoyaltyProgram

**Commits that changed its files:** 1

**Emerged in:** 1839acf54d 2025-03-25

**How:** Both classes date from the initial commit dbccd6ee4a. Catalog.PriceList provides PriceOf(isbn), and Customers.LoyaltyProgram provides DiscountFor(customerId) alongside AddPoints. Neither file changed afterwards. The pricing concern became scattered in 1839acf54d ('Quote order prices with the loyalty discount'): OrderService (Orders) imported Bookstore.Customers and added QuoteFor, which combines PriceList.PriceOf with LoyaltyProgram.DiscountFor. The concern of computing what a customer pays is thereby spread over Catalog, Customers and Orders. Before this commit, Orders used only PriceList. 146ae038ea made it worse by adding CartService.PreviewTotal, which repeats the same price-times-discount calculation with PriceList and LoyaltyProgram.

**Timeline:**

- `dbccd6ee4a`: PriceList (Catalog) and LoyaltyProgram with DiscountFor (Customers) created
- `1839acf54d`: OrderService.QuoteFor combines PriceList and LoyaltyProgram; the pricing concern is now split across components
- `146ae038ea`: CartService.PreviewTotal repeats the same price + loyalty discount calculation

**Why it is a problem:** The final price of a book for a customer is defined in three places: list prices in Catalog, discount tiers in Customers, and the combining formula duplicated in OrderService.QuoteFor and CartService.PreviewTotal. A pricing change such as a new discount rule, promotions or a different rounding means editing several components, and the copies can easily drift apart.

_Cites commits that did not change its files: 146ae038ea, 1839acf54d_

## 7. Unstable Dependency in Bookstore.Orders (Bookstore)

**Designite:** The tool detected the smell in this component because this component depends on other components that are less stable than itself. This component depends on following less stable component(s): Bookstore.Billing

**Classes:** Bookstore.Orders.Invoice; Bookstore.Orders.InvoiceService

**Commits that changed its files:** 7

**Emerged in:** b117c1ad36 2025-04-10

**How:** Orders has depended on Billing's Invoice and InvoiceService since eaa567433e (CheckoutService creates invoices). From 45ae161a74 on, Billing had no outgoing dependencies at all: InvoiceService took plain values. With instability 0, Billing could not be less stable than Orders. An earlier period in which Billing depended on Orders, from a86bbbb882 until 45ae161a74, may have produced the same smell, but that was removed in 45ae161a74. b117c1ad36 added Billing.PaymentService, which depends on OrderRepository, Order, OrderLine and OrderStatus. This gave Billing efferent coupling and raised its instability, so the existing Orders -> Billing dependency (Invoice, InvoiceService) now points at a less stable component. 9a6634f70f changed InvoiceService and PaymentService without removing this dependency.

**Timeline:**

- `eaa567433e`: CheckoutService in Orders depends on Billing's Invoice and InvoiceService
- `a86bbbb882`: InvoiceService starts depending on Orders (earlier period of Billing instability)
- `45ae161a74`: Billing's dependency on Orders removed; Billing becomes maximally stable
- `b117c1ad36`: PaymentService makes Billing depend on Orders again, so Billing becomes less stable than Orders

**Why it is a problem:** Orders is central: admin, shipping, integration, billing and reporting depend on it. Through CheckoutService it relies on InvoiceService.CreateFor and Invoice, in a Billing module that now changes along with order and payment logic. Changes in Billing's invoice API spread into checkout and from there to the many dependents of Orders.

## 8. Feature Concentration in Bookstore.Shipping (Bookstore)

**Designite:** The tool detected the smell in this component because the component realizes more than one architectural concern/feature. Independent sets of related classes within this component are: [AddressLookup' ShipmentService' ShippingNotifier' Carrier' Shipment' GiftWrap]' [PickupPoint' PickupPointDirectory]' [ReturnDesk' ReturnRequest]. LCC (Lack of Component Cohesion) = 0'3

**Classes:** Bookstore.Shipping.AddressLookup; Bookstore.Shipping.Carrier; Bookstore.Shipping.GiftWrap; Bookstore.Shipping.PickupPoint; Bookstore.Shipping.PickupPointDirectory; Bookstore.Shipping.ReturnDesk; Bookstore.Shipping.ReturnRequest; Bookstore.Shipping.Shipment; Bookstore.Shipping.ShipmentService; Bookstore.Shipping.ShippingNotifier

**Commits that changed its files:** 4

**Emerged in:** daf6018e1e 2025-04-06

**How:** c234c7eee4 created Shipping around ShipmentService, Shipment, Carrier and AddressLookup. ca5b8bd971 added ShippingNotifier, which ShipmentService uses, and a9caeed6c6 added GiftWrap, which Shipment and ShipmentService use. Up to then all classes formed one connected cluster. daf6018e1e ('Add returns and pickup points') put two unrelated features into the same namespace: PickupPoint with PickupPointDirectory, and ReturnDesk with ReturnRequest. ReturnRequest only stores a ShipmentId int, and neither pair uses nor is used by the shipment classes. The component now has three independent class groups (LCC 0.3).

**Timeline:**

- `c234c7eee4`: Shipping created with ShipmentService, Shipment, Carrier, AddressLookup
- `ca5b8bd971`: ShippingNotifier added and used by ShipmentService (same cluster)
- `a9caeed6c6`: GiftWrap added and used by Shipment and ShipmentService (same cluster)
- `daf6018e1e`: Unconnected PickupPoint/PickupPointDirectory and ReturnDesk/ReturnRequest features added

**Why it is a problem:** Returns handling, the pickup-point directory and outbound shipment creation are separate features with no code links between them, yet they share one component. Work on returns or pickup points touches and redeploys the shipping module that admin commands and reporting depend on. The namespace no longer tells readers what it is responsible for, which makes separate ownership of these features harder.

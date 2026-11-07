# Testbed for RQ2: a repo whose smells emerge in known commits

[rkacani/bookstore](https://github.com/rkacani/bookstore) is a small C# library
for an online bookstore (one project, `Bookstore`, 22 commits). Each of the
seven smells Designite detects emerges in it in one known commit, for one
visible reason. That makes it possible to check `scripts/explain.py` against an
exact answer instead of only against Designite.

The repo runs through the same pipeline as the other subject repos. The
difference is `ground_truth.json`, which records when and why each smell
emerged. It lives here and not in the repo, because the LLM can read every file
and commit there. Nothing in the repo hints at the smells.

## Usage

```bash
bash scripts/analyze.sh rkacani/bookstore       # Windows: clone into repos/ and run Designite (it is in data/screened.tsv)
python scripts/explain.py rkacani/bookstore     # the LLM explains each smell Designite found
python scripts/verify.py rkacani/bookstore      # Windows, optional: Designite's verdict on the LLM's commits
python testbed/score.py                         # compare with ground_truth.json -> output/testbed/score.csv
```

`score.py` matches each smell Designite found to the ground truth. For each
smell it writes one row with the expected commit, the commit the LLM names in
`emerged_in`, and a verdict:

| Verdict | Meaning |
|---|---|
| `correct` | the LLM names the expected commit |
| `too_early` / `too_late` | the LLM names an earlier / later commit |
| `first_emergence` | the LLM names the earlier episode of a smell that was removed and came back |
| `no_answer` | no commit, or one that is not in the repo |
| `not_in_ground_truth` | Designite found a smell the ground truth does not expect |
| `not_found_by_designite` | the ground truth expects a smell Designite did not find |

The last two mean that Designite and the ground truth disagree, which the first
run should rule out.

`score.py` also writes `output/testbed/comparison.md` for rating the
explanations by hand. For each smell it shows the expected commit and the LLM's
commit, then the ground truth's *how* next to the LLM's *how* and timeline, and
the ground truth's *why* next to the LLM's. Every commit is shown with its step,
and each smell has empty lines `Rating (how):` and `Rating (why):` to fill in.

## The story

Legend: ▲ the smell emerges in this commit, ■ present, ▽ removed in this commit.
CD = Cyclic Dependency, UD = Unstable Dependency, GC = God Component,
FC = Feature Concentration, SF = Scattered Functionality, AI = Ambiguous
Interface, DS = Dense Structure.

| Step | Commit | Message | Architectural change | CD Orders–Billing | UD Orders | UD Customers | GC Admin | FC Shipping | SF Orders | AI Integration | DS |
|---:|---|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 1 | `dbccd6ee4a` | Add catalog and customer modules | Catalog, Customers; no dependencies | | | | | | | | |
| 2 | `6c4dce7b6f` | Add order placement | Orders → Catalog | | | | | | | | |
| 3 | `eaa567433e` | Create invoices at checkout | Billing; Orders → Billing (`CheckoutService`) | | | | | | | | |
| 4 | `d47057a8ff` | Round prices and invoice amounts to cents | none (distractor: touches `OrderService`, `InvoiceService`) | | | | | | | | |
| 5 | `c234c7eee4` | Add shipping | Shipping → Orders, Customers | | | | | | | | |
| 6 | `a86bbbb882` | List the order lines on invoices | Billing → Orders (`InvoiceService.CreateFor(Order)`) | ▲ | ▲ | | | | | | |
| 7 | `7e6a95c8d6` | Add payment due dates to invoices | none (distractor: touches `Invoice`, `InvoiceService`) | ■ | ■ | | | | | | |
| 8 | `ca5b8bd971` | Send welcome, order and shipping emails | Notifications; Customers, Orders, Shipping → Notifications | ■ | ■ | | | | | | |
| 9 | `4143cc872d` | Add admin console with catalog and customer commands | Admin, 17 classes → Catalog, Customers | ■ | ■ | | | | | | |
| 10 | `e2f30f57f6` | Add partner API for marketplace orders | Integration, 5 classes, `PartnerApi` with 3 public methods → Orders | ■ | ■ | | | | | | |
| 11 | `a9caeed6c6` | Offer gift wrapping for shipments | `GiftWrap`, attached to `Shipment` (a new feature, but connected) | ■ | ■ | | | | | | |
| 12 | `1839acf54d` | Quote order prices with the loyalty discount | `OrderService.QuoteFor` uses Catalog and Customers (once) | ■ | ■ | | | | | | |
| 13 | `10a633cd5d` | Recommend books at the end of every email | Notifications → Catalog (`RecommendationBlock`) | ■ | ■ | ▲ | | | | | |
| 14 | `bfc2573685` | Add admin commands for orders and newsletters | Admin 25 classes → Orders, Notifications | ■ | ■ | ■ | | | | | |
| 15 | `45ae161a74` | Pass order data to billing as plain values | Billing no longer depends on Orders | ▽ | ▽ | ■ | | | | | |
| 16 | `a62b06d0cf` | Route all partner calls through one Handle entry point | `PartnerApi.Handle(string, object)` is the only public method | | | ■ | | | | ▲ | |
| 17 | `ce7435fa0a` | Add admin commands for shipments and invoices | Admin 32 classes → Shipping, Billing | | | ■ | ▲ | | | ■ | |
| 18 | `daf6018e1e` | Add returns and pickup points | Shipping gets two groups of classes unconnected to the rest | | | ■ | ■ | ▲ | | ■ | |
| 19 | `146ae038ea` | Show discounted prices in the shopping cart | `CartService.PreviewTotal` uses Catalog and Customers (second time) | | | ■ | ■ | ■ | ▲ | ■ | |
| 20 | `b117c1ad36` | Mark orders as paid when their invoice is settled | Billing → Orders again (`PaymentService`) | ▲ | ▲ | ■ | ■ | ■ | ■ | ■ | |
| 21 | `3c965910f7` | Add management dashboard | Reporting → all 8 other namespaces | ■ | ■ | ■ | ■ | ■ | ■ | ■ | ▲ |
| 22 | `9a6634f70f` | Tidy up order and billing code | none (distractor: touches `OrderService`, `InvoiceService`, `PaymentService`) | ■ | ■ | ■ | ■ | ■ | ■ | ■ | ■ |

To see a cause, look at the commit in which the smell emerges, e.g.
`git -C repos/rkacani_bookstore show b117c1ad36`. Every diff is short.

## What each smell tests

`ground_truth.json` has the full explanation of each smell.

| Smell | Emerges in | Why | What it tests |
|---|---|---|---|
| Cyclic Dependency Orders ↔ Billing | 20 (first in 6) | `PaymentService` loads the `Order` to mark it paid, and Orders already depends on Billing | **Re-emergence.** The cycle existed in steps 6–14 and was removed in step 15. The answer is 20, not 6. Commits 4, 7 and 22 touch the same files without changing the cycle. |
| Unstable Dependency in Orders | 20 (first in 6) | Billing uses several Orders classes but few classes use Billing, so it is less stable than Orders | **Emergence through other files.** Designite gives Orders' `CheckoutService`, but the cause is in Billing; no Orders file changed in step 20. Also re-emergence. |
| Unstable Dependency in Customers | 13 | `RecommendationBlock` gives Notifications a dependency on Catalog, which makes it less stable than Customers | **Emergence through other files.** Designite gives `CustomerService`, whose history only shows step 8. Step 13 touches only Notifications. |
| God Component Admin | 17 | 32 classes, more than 30 | **Threshold crossing.** Admin grows in three steps (17, 25, 32 classes); creating it (step 9) is not the answer. |
| Feature Concentration Shipping | 18 | Returns and pickup points form two groups that use nothing else in Shipping: 3 groups in 10 classes, LCC 0.30 > 0.2 | **Near miss.** Gift wrapping (step 11) is also a new feature, but it is attached to `Shipment`. |
| Scattered Functionality Orders (Catalog, Customers) | 19 | A second method combines `PriceList` and `LoyaltyProgram` | **Repetition.** Designite reports only repeated access; the first such method (step 12) is not enough. |
| Ambiguous Interface Integration | 16 | `Handle(string command, object payload)` replaces the explicit methods | **A refactoring that creates a smell.** |
| Dense Structure | 21 | Reporting adds 8 dependencies: 25 dependencies in 9 namespaces, average degree 5.56 > 5 | **Gradual build-up with one crossing.** Before step 21: 17 dependencies in 8 namespaces, average degree 4.25. |

## Designite's rules and the margins

Designite's rules come from the authors' description (Sharma, Singh, Spinellis:
*An empirical investigation on the relationship between design and architecture
smells*, EMSE 2020, Section 4.2). Two of them were sharpened against the
Designite results in `output/designite/`:

| Smell | Rule | Testbed, before → after emergence |
|---|---|---|
| Cyclic Dependency | a cycle of namespace dependencies | — |
| Unstable Dependency | A depends on B and I(B) > I(A), I = Ce/(Ca+Ce), counted in **classes** (not namespaces, checked on `output/designite/`) | Orders 0.38–0.67 vs Billing 0.75 (steps 6–14), 0.36–0.38 vs 0.44–0.50 (steps 20–22); Customers 0.08–0.11 vs Notifications 0.00 before step 13, 0.22–0.40 from step 13 |
| Ambiguous Interface | ≥ 5 classes and exactly one public or internal method; constructors not counted (inferred from `output/designite/`) | 3 → 1 public method in 5 classes |
| God Component | > 30 classes (or > 27,000 lines) | 25 → 32 |
| Feature Concentration | LCC = groups of related classes / classes > 0.2; one group counts as 0 | 1 group → 3 groups in 10 classes (0.30) |
| Scattered Functionality | a method accesses ≥ 2 other namespaces, and this happens more than once | 1 → 2 methods |
| Dense Structure | average degree 2E/V > 5 over all namespaces | 4.25 → 5.56 |

Everything else stays clear of these rules:
- Every namespace other than Shipping is one connected group of classes.
- Every other method and constructor accesses at most one other namespace.
- Apart from Orders ↔ Billing, the namespaces form a hierarchy.
- Every other namespace with 5 or more classes has several public methods.

## Limitations

- The expected commits come from Designite's rules as listed above, modelled
  in Python while the repo was built. Two of those rules were inferred from
  data (Ambiguous Interface ignoring constructors, Scattered Functionality
  counting methods). The first Designite run (`analyze.sh`, and `verify.py` on
  the LLM's commits) is what confirms them.
- Designite picks one namespace of a cycle to report it under. `score.py`
  therefore matches cycles by their namespaces, not by the reported one.
- A synthetic project is smaller and cleaner than real code, so results on it
  are an upper bound on what to expect from the real repos.

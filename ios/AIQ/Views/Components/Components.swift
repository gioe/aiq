// # AIQ Component Library
//
// `Views/Components/` is the canonical library for reusable UI primitives
// shared across two or more feature areas of the AIQ app.
//
// ## What belongs here
//
// A file belongs in `Views/Components/` if it meets **either** of the following:
//
// 1. **Cross-feature reuse** — the view is referenced from two or more distinct
//    feature directories (e.g., both `Dashboard/` and `Test/`).
//
// 2. **Design-system primitive** — the view encapsulates a design-token-driven
//    style (color, typography, spacing, shape) that should be applied
//    consistently throughout the app (e.g., `PrimaryButton`, `DifficultyBadge`).
//
// ## What does NOT belong here
//
// Feature-specific sub-views stay inside their feature folder. A view used
// only within `Onboarding/` lives in `Onboarding/`, not here. Only promote
// it to `Components/` when a second feature starts using it.
//
// ## Naming
//
// No prefix or suffix is required — pick a name that describes the concept,
// not the location (e.g., `ToastView`, not `CommonToastView`).

# Coding Standards Update: Localization Workflow

## Overview

Update `ios/docs/CODING_STANDARDS.md` to include explicit guidance on localization for error messages and user-facing text, preventing workflow gaps where localization keys are forgotten.

## Strategic Context

### Problem Statement

Developers adding new error enums or user-facing features may forget to add corresponding localization strings to `Localizable.strings`. This is because:
- The dependency between Swift code and `.strings` files is not enforced
- No explicit checklist exists in the coding standards
- Missing keys fail silently (showing raw key to users)

### Success Criteria

- Coding standards include clear guidance on when and how to add localization strings
- Checklists provide actionable steps for common workflows
- Developers can reference the document when implementing errors or UI features
- Missing localization keys are caught during development or code review

### Why Now?

The BTS-137 implementation raised awareness of this workflow gap. While that specific PR included the localization string, the question highlights a legitimate documentation need that should be addressed proactively.

## Technical Approach

### High-Level Architecture

Update `CODING_STANDARDS.md` with three new sections:

1. **Localization for Errors** (subsection under Error Handling)
   - When to use `NSLocalizedString`
   - Process for adding keys
   - Common mistakes to avoid

2. **Common Implementation Workflows** (new section)
   - Pre-implementation checklists
   - Step-by-step guides for common tasks

3. **Error Enum Naming Patterns** (subsection under Error Handling)
   - Consistent key naming conventions
   - Examples by error domain

### Key Decisions & Tradeoffs

**Decision 1: Documentation-First Approach**
- **Why:** Low effort, immediate impact, no build system changes
- **Tradeoff:** Relies on developers reading the docs (mitigated by code review)
- **Alternative considered:** Build-time validation script (higher maintenance, added later if needed)

**Decision 2: Checklist Format**
- **Why:** Checklists are actionable and easy to follow
- **Tradeoff:** Requires maintenance as workflow evolves
- **Alternative considered:** Prose-only documentation (less actionable)

**Decision 3: Location in CODING_STANDARDS.md**
- **Why:** Existing document is the source of truth for iOS development
- **Tradeoff:** Already a long document (2273 lines)
- **Mitigation:** Use clear MARK sections and table of contents

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Developers don't read updated docs | Medium | Mention in PR reviews, link in comments |
| Checklist becomes outdated | Low | Review quarterly, update as needed |
| Document becomes too long | Low | Use clear sections, maintain ToC |

## Implementation Plan

### Phase 1: Core Documentation Updates

**Goal:** Add essential localization guidance to CODING_STANDARDS.md

**Duration:** 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 1.1 | Read existing Error Handling section (lines 463-616) | None | 15 min | Understand current structure |
| 1.2 | Draft "Localization for Errors" subsection | 1.1 | 30 min | Include examples, common mistakes |
| 1.3 | Add subsection after line 616 in CODING_STANDARDS.md | 1.2 | 15 min | Insert under Error Handling section |
| 1.4 | Draft "Error Enum Naming Patterns" subsection | 1.1 | 20 min | Table format with examples |
| 1.5 | Add naming patterns subsection after 1.3 | 1.4 | 10 min | Maintains logical flow |
| 1.6 | Update Table of Contents | 1.3, 1.5 | 10 min | Add new subsections |

### Phase 2: Implementation Workflow Checklists

**Goal:** Add actionable checklists for common development tasks

**Duration:** 1-2 hours

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 2.1 | Identify appropriate location for new section | 1.6 | 10 min | After Error Handling, before Networking |
| 2.2 | Draft "Common Implementation Workflows" section | 2.1 | 30 min | Two checklists: errors and features |
| 2.3 | Add new section to CODING_STANDARDS.md | 2.2 | 15 min | Line ~617 (after Error Handling) |
| 2.4 | Update Table of Contents with new section | 2.3 | 10 min | Add to ToC |
| 2.5 | Review entire document for consistency | 2.4 | 20 min | Check formatting, links |

### Phase 3: Review and Validation

**Goal:** Ensure updates are clear, accurate, and actionable

**Duration:** 30 minutes

| Task ID | Task | Dependencies | Estimate | Notes |
|---------|------|--------------|----------|-------|
| 3.1 | Self-review: clarity and completeness | 2.5 | 15 min | Read as if unfamiliar with topic |
| 3.2 | Verify examples compile and are accurate | 3.1 | 10 min | Check Swift syntax, key names |
| 3.3 | Update gap analysis doc with implementation status | 3.2 | 5 min | Record what was implemented |

## Detailed Content Specifications

### Section 1: Localization for Errors

**Location:** Under "Error Handling" section (after line 616)

**Content includes:**
- When to use localization (all `LocalizedError` implementations)
- Step-by-step process (define → implement → add strings → test)
- Code example showing Swift enum and corresponding `.strings` entries
- Verification steps
- Common mistakes table

**Length:** ~50 lines

### Section 2: Common Implementation Workflows

**Location:** New section after "Error Handling" (~line 617)

**Content includes:**
- Two checklists:
  1. Adding new error types (8 items)
  2. Adding features with user-facing text (7 items)
- Clear formatting with `- [ ]` checkboxes
- Brief explanation for each item

**Length:** ~40 lines

### Section 3: Error Enum Naming Patterns

**Location:** Under "Error Handling" section (after Localization subsection)

**Content includes:**
- Table with 4 columns: Error Type | Key Pattern | Example | Usage
- Consistency rules (bullet list)
- Reference to `Localizable.strings` structure

**Length:** ~30 lines

## Open Questions

1. Should we also add a "Localization" top-level section for broader i18n topics?
   - **Recommendation:** Start with error-specific guidance, add broader section later if needed

2. Should we include the validation script in the repo?
   - **Recommendation:** Document it in the gap analysis, implement only if manual process fails

3. Should we update the PR template to include localization checks?
   - **Recommendation:** Yes, as Phase 4 (separate from CODING_STANDARDS update)

## Success Metrics

- [ ] CODING_STANDARDS.md includes 3 new subsections on localization
- [ ] Table of Contents is updated with new sections
- [ ] Document length increases by ~120 lines (5% growth)
- [ ] Examples compile and reference real files
- [ ] Checklists are actionable (no vague items)
- [ ] Gap analysis document is updated with implementation status

## Appendix A: Example Content Preview

### Localization for Errors

```markdown
### Localization for Errors

All user-facing error enums conforming to `LocalizedError` MUST have corresponding entries in `Localizable.strings`.

**Process:**
1. Define error enum with cases
2. Implement `errorDescription` using `NSLocalizedString`
3. **IMMEDIATELY** add corresponding keys to `ios/AIQ/en.lproj/Localizable.strings`
4. Test that error messages display correctly (not raw keys)

**Example:**
[Swift code and strings file examples...]

**Verification:**
- Run the app and trigger the error
- Verify the localized message appears
- Check that the message is user-friendly

**Common Mistakes:**
| Mistake | Impact | Solution |
|---------|--------|----------|
| Forgetting strings entry | Raw key shown to users | Follow process step 3 |
[More mistakes...]
```

## Appendix B: Files to Modify

1. **ios/docs/CODING_STANDARDS.md**
   - Line ~616: Add "Localization for Errors" subsection
   - Line ~617: Add "Common Implementation Workflows" section
   - Line ~15: Update Table of Contents
   - Estimated additions: ~120 lines

2. **docs/analysis/localization-workflow-gap-analysis.md**
   - Add implementation status section
   - Link to updated CODING_STANDARDS.md
   - Estimated additions: ~10 lines

## Next Steps

After implementing this plan:

1. **Create PR** with CODING_STANDARDS.md updates
2. **Announce in team** (Slack/email) highlighting new localization guidance
3. **Update PR template** to include localization checklist (separate PR)
4. **Monitor effectiveness** by tracking PRs with missing localization keys (should be 0)
5. **Consider validation script** only if manual process fails (3+ months from now)

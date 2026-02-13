# Documentation PR Checklist

Use this checklist for PRs that add or modify:
- Coverage reports
- Analysis documents
- Architecture documentation
- Process improvement proposals
- README files with technical claims
- CODING_STANDARDS.md sections (especially technical procedures)
- Emergency runbooks and recovery documentation
- Configuration guides with file path references

## Metadata Accuracy

- [ ] All ticket references (BTS-XXX, etc.) verified to exist in Jira
- [ ] Tickets that don't exist yet are labeled as "Proposed: BTS-XXX"
- [ ] Branch name in document matches actual branch/ticket ID
- [ ] Dates are current and accurate (not copy-pasted from previous docs)
- [ ] Author/team attribution is correct

## Technical Accuracy

- [ ] All file paths verified to exist in the codebase
- [ ] All line counts explained (e.g., "executable lines" vs "total lines")
- [ ] All code snippets tested/verified to work
- [ ] Claims about "unused code" verified by searching for references
- [ ] All metrics include units and context
- [ ] Version numbers and tool versions are current

## Clarity for Future Readers

- [ ] Domain-specific terms defined on first use (e.g., "executable lines")
- [ ] Distinguish between "proposed" and "existing" work items
- [ ] Assumptions documented explicitly
- [ ] Links use paths that will remain stable

## Cross-References

- [ ] References to CODING_STANDARDS.md are accurate
- [ ] Related documents linked where appropriate
- [ ] No contradictions with existing documentation
- [ ] External links verified to be accessible

## Coverage Reports (Additional)

When creating coverage reports specifically:

- [ ] Clarify executable vs total line counts
- [ ] Verify files marked as "0% coverage" are actually executed in production
- [ ] Check that "unused code" claims are verified by searching imports/references
- [ ] Prioritization considers security/risk impact, not just coverage percentage
- [ ] Testing standards from CODING_STANDARDS.md are referenced where applicable

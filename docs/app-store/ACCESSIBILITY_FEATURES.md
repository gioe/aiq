# AIQ App Store Accessibility Features

This document contains the accessibility feature descriptions for App Store Connect metadata. Copy these sections directly into App Store Connect when updating the app listing.

---

## App Store Description - Accessibility Section

Add the following to the end of the App Store description:

```
ACCESSIBILITY

AIQ is designed to be accessible to everyone. We've built comprehensive accessibility support so all users can track their cognitive health:

- Full VoiceOver Support: Every screen, button, and interactive element is optimized for screen reader users with descriptive labels and contextual hints
- Dynamic Type: Text scales smoothly with your preferred system font size, from small to accessibility sizes
- Reduce Motion: Respects your motion preferences with alternative fade transitions when reduced motion is enabled
- High Contrast Colors: WCAG AA compliant color contrast ratios ensure text is readable in both light and dark modes
- Touch Accessibility: All interactive elements meet the 44x44 point minimum touch target requirement
```

---

## App Store Promotional Text (170 characters max)

```
Track your cognitive health with full VoiceOver, Dynamic Type, and Reduce Motion support. Accessible IQ testing for everyone.
```

---

## App Store Keywords (Add to existing keywords)

```
accessibility, voiceover, screen reader, dynamic type, accessible, wcag, reduce motion
```

---

## What's New - Accessibility Update

Use this for version release notes when highlighting accessibility improvements:

```
Accessibility Enhancements:
- Complete VoiceOver support across all screens
- Dynamic Type scaling for improved readability
- Reduce Motion support for motion-sensitive users
- WCAG AA compliant color contrast
- Optimized touch targets throughout the app
```

---

## Detailed Accessibility Features Reference

### VoiceOver Support
- **30+ views** with comprehensive screen reader support
- Descriptive accessibility labels on all interactive elements
- Contextual hints explaining button actions and navigation
- Properly grouped elements for logical screen reader navigation
- Live updates for timer and progress indicators
- Decorative elements hidden from screen readers

### Dynamic Type
- Centralized Typography system ensuring consistent text scaling
- All text uses semantic font styles (Title, Body, Caption)
- Custom @ScaledMetric implementation for specialized layouts
- IQ score displays scale appropriately at all text sizes
- No truncation issues at largest accessibility text sizes

### Reduce Motion
- 18 view files respect the Reduce Motion system setting
- Spring animations disabled when Reduce Motion is on
- Opacity-only transitions as accessible alternatives
- Timer animations simplified for motion-sensitive users
- Card transitions use fade instead of slide when preferred

### Color Accessibility
- WCAG 2.1 Level AA compliance throughout
- Primary text: 21:1 contrast ratio (black on white)
- Secondary text: 7.2:1 contrast ratio
- Semantic colors with accessible text variants
- Full light mode and dark mode support
- Performance indicators use compliant color variants

### Touch Accessibility
- Minimum 44x44 point touch targets on all buttons
- IconButton component enforces touch target compliance
- Adequate spacing between interactive elements
- Clear visual feedback on touch interactions

---

## App Store Connect Checklist

Before submitting, verify the following in App Store Connect:

- [ ] Accessibility section added to app description
- [ ] Promotional text updated with accessibility keywords
- [ ] Keywords include accessibility-related terms
- [ ] Screenshots include examples with larger text sizes (optional)
- [ ] What's New mentions accessibility for relevant updates

---

## Apple Accessibility Features Checklist

When prompted for accessibility features in App Store Connect, select:

- [x] VoiceOver
- [x] Dynamic Type
- [x] Reduce Motion
- [x] Increase Contrast (partial - color compliant)

---

*Last updated: January 2026*
*Based on accessibility audit of AIQ iOS app v1.0*

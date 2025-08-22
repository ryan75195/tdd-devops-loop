# Claude Development Guidelines

## Core Principles

### ❌ NO FALLBACK CODE
- **Never implement fallback mechanisms** without explicit user approval
- When something fails, **investigate the root cause** and fix the actual problem
- **Ask the user** if you're unsure how to proceed instead of creating workarounds

### 🎯 Problem-Solving Approach
1. **Identify the exact error** - Don't mask failures with fallbacks
2. **Research the root cause** - Understand why something isn't working
3. **Ask clarifying questions** if the solution isn't clear
4. **Implement the correct fix** - Address the underlying issue

### 🔧 Code Quality Standards
- Write code that works correctly the first time
- Use proper error handling that exposes issues, not hides them
- Prefer explicit failure over silent degradation
- Always validate assumptions rather than assume fallbacks are needed

### 💬 Communication
- When encountering failures, explain what's wrong and why
- Present options to the user rather than choosing workarounds
- Be transparent about limitations and unknowns

---

**Remember: The user prefers to fix the real problem rather than work around it.**
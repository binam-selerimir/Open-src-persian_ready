# Full Markdown Feature Test

This file tests ALL supported markdown features in OpenSrcPersian.

---

## 1. Basic Formatting

**Bold text** and *italic text* and ~~strikethrough~~ and `inline code`.

Bold with asterisks: **bold** and __bold__.
Italic with asterisks: *italic* and _italic_.

---

## 2. Headings

### Level 3 Heading

#### Level 4 Heading

---

## 3. Links and Images

[Open Source Initiative](https://opensource.org)

[Link with title](https://example.com "Example Title")

---

## 4. Lists

### Unordered List

- Item one
- Item two
  - Nested item
  - Another nested item
- Item three

### Ordered List

1. First step
2. Second step
   1. Sub-step A
   2. Sub-step B
3. Third step

---

## 5. Blockquotes

> This is a blockquote.
>
> It can span multiple paragraphs.

> Nested blockquote
>> Level 2 blockquote

---

## 6. Code Blocks

### Fenced Code (Python)

```python
def fibonacci(n):
    """Generate Fibonacci sequence."""
    a, b = 0, 1
    result = []
    for _ in range(n):
        result.append(a)
        a, b = b, a + b
    return result

print(fibonacci(10))
```

### Fenced Code (JavaScript)

```javascript
const debounce = (fn, delay) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
};
```

### Fenced Code (Bash)

```bash
#!/bin/bash
echo "Hello, World!"
for i in {1..5}; do
  echo "Iteration $i"
done
```

### Fenced Code (No Language)

```
plain code block
no syntax highlighting
```

---

## 7. Tables

| Feature | Status | Notes |
|---------|--------|-------|
| Admonitions | Supported | !!! note, !!! warning, etc. |
| LaTeX Math | Supported | $...$ and $$...$$ syntax |
| Code Highlighting | Supported | fenced_code with language |
| Tables | Supported | Standard markdown tables |

### Table Alignment

| Left | Center | Right |
|:-----|:------:|------:|
| L1 | C1 | R1 |
| L2 | C2 | R2 |

---

## 8. Admonitions

### Note

!!! note
    This is a note admonition.
    It can span multiple paragraphs.

### Warning

!!! warning
    This is a warning. Be careful!

### Danger

!!! danger "Critical Warning"
    This is a custom-titled danger block.

### Tip

!!! tip
    Here is a helpful tip.

### Info

!!! info
    Informational content here.

### Hint

!!! hint
    A hint for the reader.

### Attention

!!! attention
    Pay attention to this!

### Caution

!!! caution
    Use caution when proceeding.

### Empty Title (no title bar)

!!! important ""
    This admonition has no title bar.

---

## 9. LaTeX Math

### Inline Math

The quadratic formula is $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.

Euler's identity: $e^{i\pi} + 1 = 0$.

Alternative inline syntax: \(E = mc^2\).

### Block Math

$$
\int_{-\infty}^{\infty} e^{-x^2} \, dx = \sqrt{\pi}
$$

### Aligned Equations

$$
\begin{align}
    \nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\
    \nabla \cdot \mathbf{B} &= 0 \\
    \nabla \times \mathbf{E} &= -\frac{\partial \mathbf{B}}{\partial t} \\
    \nabla \times \mathbf{B} &= \mu_0 \mathbf{J} + \mu_0 \varepsilon_0 \frac{\partial \mathbf{E}}{\partial t}
\end{align}
$$

### Matrix

$$
\mathbf{A} = \begin{pmatrix}
    a_{11} & a_{12} & \cdots & a_{1n} \\
    a_{21} & a_{22} & \cdots & a_{2n} \\
    \vdots & \vdots & \ddots & \vdots \\
    a_{n1} & a_{n2} & \cdots & a_{nn}
\end{pmatrix}
$$

### Summation

$$
\sum_{i=1}^{n} i^2 = \frac{n(n+1)(2n+1)}{6}
$$

### Alternative Block Syntax

\[
E = mc^2
\]

---

## 10. Horizontal Rules

---

***

___

---

## 11. Mixed Content

Here is a paragraph with **bold**, *italic*, and `code`.

!!! note
    This note contains **bold** and *italic* text.

    It also has a code block:

    ```python
    x = 42
    ```

And a math formula: $f(x) = x^2$.

| Column 1 | Column 2 |
|----------|----------|
| Value A  | $alpha$  |
| Value B  | $beta$   |

---

## 12. Nested Structures

> This blockquote contains:
>
> - A list item
> - Another item
>
> And a math formula: $e^{i\pi} = -1$

---

## 13. XSS Prevention Test

The following should be sanitized:

<script>alert('xss')</script>

<img src="x" onerror="alert('xss')">

<a href="javascript:alert('xss')">click</a>

**These should NOT render as HTML.**

---

## 14. Edge Cases

Empty emphasis: **  and  **

Unclosed code: `not closed

Special characters: < > & " '

Unicode: 你好 مرحبا 🌍

---

*End of test document.*

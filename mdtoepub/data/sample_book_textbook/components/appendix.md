A continuacion se presentan recursos adicionales organizados por tema, junto con una breve descripcion de cada uno.

## Libros recomendados

| Titulo | Autor | Tema |
|--------|-------|------|
| *Mindset* | Carol Dweck | Mentalidad de crecimiento |
| *Make It Stick* | Brown, Roediger, McDaniel | Ciencia del aprendizaje |
| *El Cerebro que Aprende* | Francisco Mora | Neuroeducacion |
| *Atomic Habits* | James Clear | Formacion de habitos |
| *Deep Work* | Cal Newport | Concentracion profunda |
| *Thinking, Fast and Slow* | Daniel Kahneman | Sesgos cognitivos |

## Articulos academicos

Para los lectores que quieran profundizar en la investigacion original:

- Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning. *Psychological Science*.
- Dunlosky, J., et al. (2013). Improving students' learning with effective learning techniques. *Psychological Science in the Public Interest*.

## Herramientas digitales

**Anki** (ankiweb.net): Aplicacion de repaso espaciado gratuita y multiplataforma. Permite crear tus propias tarjetas de memoria y programar repasos segun el algoritmo de SM-2.
{.tip}

**Forest** (forestapp.cc): App que te ayuda a mantener la concentracion plantando arboles virtuales. Si abandonas la tarea, el arbol se marchita.
{.tip}

## Codigo de ejemplo para seguimiento de aprendizaje

Si te gusta la programacion, puedes crear un sistema sencillo para registrar tu progreso:

```python
import json
from datetime import datetime, timedelta

class LearningTracker:
    def __init__(self):
        self.sessions = []

    def add_session(self, topic, duration, technique):
        self.sessions.append({
            "topic": topic,
            "duration": duration,
            "technique": technique,
            "date": datetime.now().isoformat()
        })

    def get_review_dates(self, initial_date):
        return {
            "first_review": initial_date + timedelta(days=1),
            "second_review": initial_date + timedelta(days=7),
            "third_review": initial_date + timedelta(days=30)
        }

tracker = LearningTracker()
tracker.add_session("Atencion", 25, "Pomodoro")
```

**Nota:** El codigo anterior es un ejemplo simplificado. Puedes adaptarlo a tus necesidades o crear tu propio sistema de seguimiento.
{.note}

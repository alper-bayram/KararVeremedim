from django import forms

from .models import MAX_OPTIONS, MIN_OPTIONS, Category
from .services import (
    DEFAULT_DURATION,
    DESCRIPTION_MAX,
    DURATION_CHOICES,
    OPTION_MAX,
    QUESTION_MAX,
    QUESTION_MIN,
)

OPTION_FIELDS = [f"option_{number}" for number in range(1, MAX_OPTIONS + 1)]


class PollForm(forms.Form):
    question = forms.CharField(
        label="Sorunu yaz",
        min_length=QUESTION_MIN,
        max_length=QUESTION_MAX,
        error_messages={
            "required": "Bir soru yazmalısın.",
            "min_length": f"Soru en az {QUESTION_MIN} karakter olmalı.",
            "max_length": f"Soru en fazla {QUESTION_MAX} karakter olabilir.",
        },
        widget=forms.Textarea(
            attrs={
                "class": "field__input",
                "rows": 3,
                "maxlength": QUESTION_MAX,
                "placeholder": "Örn. Bu akşam sinemaya mı gitsem, restorana mı?",
                "data-counter": QUESTION_MAX,
            }
        ),
    )
    description = forms.CharField(
        label="Açıklama (opsiyonel)",
        required=False,
        max_length=DESCRIPTION_MAX,
        error_messages={"max_length": f"Açıklama en fazla {DESCRIPTION_MAX} karakter olabilir."},
        widget=forms.Textarea(
            attrs={
                "class": "field__input",
                "rows": 3,
                "maxlength": DESCRIPTION_MAX,
                "placeholder": "Kararına yardımcı olacak biraz bağlam ekleyebilirsin.",
                "data-counter": DESCRIPTION_MAX,
            }
        ),
    )
    category = forms.ChoiceField(
        label="Kategori",
        choices=Category.choices,
        error_messages={
            "required": "Bir kategori seçmelisin.",
            "invalid_choice": "Geçerli bir kategori seç.",
        },
        widget=forms.RadioSelect,
    )
    duration = forms.ChoiceField(
        label="Süre",
        choices=DURATION_CHOICES,
        initial=DEFAULT_DURATION,
        error_messages={"invalid_choice": "Geçerli bir süre seç."},
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # option_1 ... option_5: blank ones are dropped on the server.
        for index, name in enumerate(OPTION_FIELDS, start=1):
            self.fields[name] = forms.CharField(
                label=f"Seçenek {index}",
                required=False,
                max_length=OPTION_MAX,
                error_messages={"max_length": f"Seçenek en fazla {OPTION_MAX} karakter olabilir."},
                widget=forms.TextInput(
                    attrs={
                        "class": "field__input",
                        "maxlength": OPTION_MAX,
                        "placeholder": f"Seçenek {index}",
                    }
                ),
            )

    def option_fields(self):
        """Bound option fields in order, for the template."""
        return [self[name] for name in OPTION_FIELDS]

    def clean(self):
        cleaned = super().clean()
        filled = [(name, cleaned.get(name, "").strip()) for name in OPTION_FIELDS]
        filled = [(name, value) for name, value in filled if value]

        # Only judge the option count when no individual option failed validation.
        if any(name in self.errors for name in OPTION_FIELDS):
            return cleaned

        if len(filled) < MIN_OPTIONS:
            empty = next(name for name in OPTION_FIELDS if not cleaned.get(name, "").strip())
            self.add_error(empty, f"En az {MIN_OPTIONS} seçenek girmelisin.")
            return cleaned

        seen = set()
        for name, value in filled:
            key = value.lower()
            if key in seen:
                self.add_error(name, "Bu seçenek zaten eklenmiş.")
            seen.add(key)

        cleaned["options"] = [value for _, value in filled]
        return cleaned

from django import forms
from django.core.exceptions import ValidationError

from modules.green.models import Penyedia

from .models import Hadiah, Mitra


INPUT_CLASS = (
    'mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 '
    'focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'
)
EMERALD_INPUT_CLASS = INPUT_CLASS.replace('blue', 'emerald')


class MitraForm(forms.ModelForm):
    class Meta:
        model = Mitra
        fields = ['nama_mitra', 'email_mitra', 'tanggal_kerja_sama']
        widgets = {
            'nama_mitra': forms.TextInput(attrs={
                'class': EMERALD_INPUT_CLASS,
                'placeholder': 'Masukkan nama perusahaan/organisasi mitra...',
            }),
            'email_mitra': forms.EmailInput(attrs={
                'class': EMERALD_INPUT_CLASS,
                'placeholder': 'Contoh: partnership@mitra.com',
            }),
            'tanggal_kerja_sama': forms.DateInput(attrs={
                'class': EMERALD_INPUT_CLASS,
                'type': 'date',
            }, format='%Y-%m-%d'),
        }


class MitraEditForm(MitraForm):
    class Meta(MitraForm.Meta):
        fields = ['nama_mitra', 'tanggal_kerja_sama']


class HadiahForm(forms.ModelForm):
    class Meta:
        model = Hadiah
        fields = [
            'nama_hadiah',
            'id_penyedia',
            'harga_miles',
            'deskripsi',
            'valid_start_date',
            'program_end',
        ]
        widgets = {
            'nama_hadiah': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Masukkan nama hadiah...',
            }),
            'id_penyedia': forms.Select(attrs={
                'class': INPUT_CLASS + ' bg-white',
            }),
            'harga_miles': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Contoh: 1500',
                'min': 1,
            }),
            'deskripsi': forms.Textarea(attrs={
                'class': INPUT_CLASS,
                'rows': 3,
                'placeholder': 'Tuliskan deskripsi lengkap hadiah...',
            }),
            'valid_start_date': forms.DateInput(attrs={
                'class': INPUT_CLASS,
                'type': 'date',
            }, format='%Y-%m-%d'),
            'program_end': forms.DateInput(attrs={
                'class': INPUT_CLASS,
                'type': 'date',
            }, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_penyedia'].queryset = Penyedia.objects.all().order_by('id')
        self.fields['id_penyedia'].label_from_instance = self._penyedia_label

    def clean(self):
        cleaned_data = super().clean()
        valid_start_date = cleaned_data.get('valid_start_date')
        program_end = cleaned_data.get('program_end')

        if valid_start_date and program_end and program_end < valid_start_date:
            raise ValidationError('Tanggal akhir program tidak boleh lebih awal dari tanggal mulai.')

        return cleaned_data

    @staticmethod
    def _penyedia_label(penyedia):
        mitra = getattr(penyedia, 'mitra', None)
        if mitra:
            return f"{mitra.nama_mitra} (Mitra)"

        maskapai = penyedia.maskapai_set.first()
        if maskapai:
            return f"{maskapai.nama_maskapai} (Maskapai)"

        return f"Penyedia {penyedia.pk}"

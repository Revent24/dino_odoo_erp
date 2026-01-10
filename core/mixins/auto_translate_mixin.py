import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class BaseTranslator(object):
    def translate(self, text, dest):
        raise NotImplementedError()


class GoogleTransAdapter(BaseTranslator):
    def __init__(self):
        try:
            from googletrans import Translator as GT
            try:
                self._t = GT()
            except Exception:
                try:
                    self._t = GT(http2=False)
                except Exception:
                    self._t = None
        except Exception:
            self._t = None

    def translate(self, text, dest):
        if not self._t:
            raise RuntimeError('googletrans not available')
        try:
            return self._t.translate(text, dest=dest).text
        except Exception:
            try:
                from googletrans import Translator as GT
                t2 = GT(http2=False)
                return t2.translate(text, dest=dest).text
            except Exception as e:
                raise


class AutoTranslateMixin(models.AbstractModel):
    _name = 'mixin.auto.translate'
    _description = 'Auto Translate Mixin'

    _auto_translate_exclude_fields = []

    def _get_fields_to_translate(self):
        try:
            base = super(AutoTranslateMixin, self)._get_fields_to_translate()
        except Exception:
            base = []
        if base:
            return base

        fields = []
        for name, field in getattr(self, '_fields', {}).items():
            if getattr(field, 'translate', False) and field.type in ('char', 'text', 'html'):
                fields.append(name)

        exclude = getattr(self, '_auto_translate_exclude_fields', []) or []
        return [f for f in fields if f not in exclude]

    def _get_target_languages(self):
        return [r.code for r in self.env['res.lang'].search([])]

    def _get_translator(self):
        provider = self.env['ir.config_parameter'].sudo().get_param('dino_auto_translate.provider', 'googletrans')
        if provider == 'googletrans':
            return GoogleTransAdapter()
        raise RuntimeError('No translator available for provider %s' % provider)

    def write(self, vals):
        res = super(AutoTranslateMixin, self).write(vals)

        if self.env.context.get('skip_translation'):
            return res

        fields_to_translate = self._get_fields_to_translate() or []
        intersect = set(vals.keys()) & set(fields_to_translate)
        if not intersect:
            return res

        try:
            translator = self._get_translator()
        except Exception as e:
            _logger.warning('AutoTranslate: no translator available (%s)', e)
            return res

        target_langs = self._get_target_languages() or []
        active_lang = self.env.user.lang

        for record in self:
            for field in intersect:
                source_text = vals.get(field) or getattr(record, field) or ''
                if not source_text:
                    continue

                for lang in target_langs:
                    if not lang or lang == active_lang:
                        continue
                    google_code = lang.split('_')[0]
                    try:
                        translated = translator.translate(source_text, dest=google_code)
                        record.with_context(lang=lang, skip_translation=True).write({field: translated})
                    except Exception as e:
                        _logger.warning('AutoTranslate failed for %s.%s -> %s: %s', record._name, field, lang, e)

        return res
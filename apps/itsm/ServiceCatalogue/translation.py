from modeltranslation.translator import translator, TranslationOptions
from simple_history import register
from .models import Service, ServiceCategory, ServiceRevision, Clientele, FeeUnit


class ServiceTranslationOptions(TranslationOptions):
    fields = ("name", "purpose")
    required_languages = {
        "default": (
            "name",
            "purpose",
        )
    }


translator.register(Service, ServiceTranslationOptions)
register(Service)  # simple history


class ServiceCategoryTranslationOptions(TranslationOptions):
    fields = ("name", "description")
    required_languages = {"default": ("name",)}


translator.register(ServiceCategory, ServiceCategoryTranslationOptions)
register(ServiceCategory)  # simple history


class ServiceRevisionTranslationOptions(TranslationOptions):
    fields = (
        "keywords",
        "description",
        "requirements",
        "usage_information",
        "details",
        "options",
        "service_level",
    )


translator.register(ServiceRevision, ServiceRevisionTranslationOptions)
register(ServiceRevision)  # simple history


class ClienteleTranslationOptions(TranslationOptions):
    fields = ("name",)


translator.register(Clientele, ClienteleTranslationOptions)
register(Clientele)  # simple history


class FeeUnitTranslationOptions(TranslationOptions):
    fields = ("name",)


translator.register(FeeUnit, FeeUnitTranslationOptions)
register(FeeUnit)  # simple history

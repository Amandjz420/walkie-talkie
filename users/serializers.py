from rest_framework import serializers

from common.choices import InputLanguageMode
from users.models import User


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "display_name", "preferred_output_language")


class UserSerializer(serializers.ModelSerializer):
    is_demo_user = serializers.SerializerMethodField()
    effective_input_language = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "display_name",
            "preferred_output_language",
            "input_language_mode",
            "manual_input_language",
            "effective_input_language",
            "is_demo_user",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_is_demo_user(self, obj):
        return not bool(obj.email)

    def get_effective_input_language(self, obj):
        if obj.input_language_mode == InputLanguageMode.MANUAL:
            return obj.manual_input_language
        return "auto"


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("display_name", "preferred_output_language", "input_language_mode", "manual_input_language")

    def validate(self, attrs):
        mode = attrs.get("input_language_mode", getattr(self.instance, "input_language_mode", None))
        manual_language = attrs.get(
            "manual_input_language", getattr(self.instance, "manual_input_language", None)
        )
        if mode == InputLanguageMode.MANUAL and not manual_language:
            raise serializers.ValidationError(
                {"manual_input_language": "Manual input language is required when mode is manual."}
            )
        return attrs


class DemoLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    display_name = serializers.CharField(max_length=120)
    preferred_output_language = serializers.CharField(max_length=16, default="en")

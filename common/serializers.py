from rest_framework import serializers


class AbsoluteURLSerializerMixin(serializers.Serializer):
    def build_absolute_uri(self, url: str | None) -> str | None:
        if not url:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

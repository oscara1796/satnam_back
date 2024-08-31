from rest_framework import serializers

from .models import SubscriptionPlan


class PaymentMethodSerializer(serializers.Serializer):
    number = serializers.CharField(max_length=16)
    exp_month = serializers.IntegerField(min_value=1, max_value=12)
    exp_year = serializers.IntegerField(min_value=2022, max_value=9999)
    cvc = serializers.CharField(max_length=4)


class StripePriceSerializer(serializers.Serializer):
    price_id = serializers.CharField(max_length=100)

    def validate_price_id(self, value):
        # Perform custom validation for the Stripe price ID
        if not value.startswith("price_"):
            raise serializers.ValidationError("Invalid Stripe price ID")

        return value


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"

    def validate_features(self, value):
        # Just an example: Ensure that each item is a dictionary with a 'name' key
        if isinstance(value, list) and all(
            isinstance(item, dict) and "name" in item for item in value
        ):
            return value
        else:
            raise serializers.ValidationError(
                "Features must be a list of dictionaries with a 'name' key."
            )

    def validate_metadata(self, value):
        # Check if metadata is a dictionary (simple validation example)
        if isinstance(value, dict):
            return value
        else:
            raise serializers.ValidationError("Metadata must be a valid JSON object.")

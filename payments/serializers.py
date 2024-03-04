from rest_framework import serializers


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

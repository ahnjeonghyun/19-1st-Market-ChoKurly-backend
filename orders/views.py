import json
import jwt
import my_settings

from .models            import Order, ShippingMethod,OrderStatus,Cart,PaymentType
from users.models       import User, Address
from users.decorators   import login_required
from products.models    import Product

from django.db.models   import Q
from django.http        import JsonResponse
from django.views       import View
from django.db          import transaction

class OrderformView(View):
    @login_required
    def get(self, request):
        if Order.objects.filter(Q(user_id = request.user) & Q(order_status_id = 1) | Q(order_status_id = 2)).exists():
            ordercheck   = Order.objects.get(user_id = request.user)
            
            if ordercheck.total_price > 10000.00:
                ordercheck.shipping_price = None
                ordercheck.save()

            products=[{
                'product_id': product.product.id,
                'product_name': product.product.name,
                'product_quantity': product.quantity,
                'product_thumbnail_image': product.product.thumbnail_image,
                'product_price': int(product.product.price),
                'product_discount_price': int(product.product.price - ( product.product.discount_rate.discount_rate * product.product.price if product.product.discount_rate.discount_rate else None)),
            }for product in ordercheck.cart_set.all()]

            result=[{
                'order_product':products,
                'user_name': request.user.name,
                'user_phone':request.user.phone_number,
                'user_email':request.user.email,
                'user_address': request.user.address_set.get(is_default=1).address,
                'shipping_price': ordercheck.shipping_price
                } ]

            ordercheck.order_status_id = 2
            ordercheck.save()
            return JsonResponse({'result':result}, status=200)   

        return JsonResponse({'MESSAGE':'Don\'t have anything to order'}, status=400)

class OrderDetailView(View):
    @login_required
    def post(self,request):
        
        if Order.objects.filter(Q(user_id=request.user) & Q(order_status_id = 3)).exists():

            orders = Order.objects.filter(user_id=request.user)

            result=[
                {'order_id':order.id,
                'order_date':order.updated_at,
                'total_price':order.total_price, 
                'products':order.cart_set.first().product.name,
                'delivery_status':order.delivery_status.name,
                'products_thumbnail':order.cart_set.first().product.thumbnail_image,
                }for order in orders]

            return JsonResponse({'result':result}, status=201)

        return JsonResponse({'MESSAGE':False}, status=400)

class BasketView(View):
    @login_required
    def get(self, request):
        user                   = request.user
        order                  = Order.objects.filter(Q(user_id=user.id) & Q(order_status=1)).first()
        cart_list              = order.cart_set.all() if order else None

        result                 = [{
            'id'                   : '1',
            'user_id'              : user.id,
            'cart_product_info'    : [{
                'id'                : '{}'.format(i+1),
                'product_id'        : cart_list[i].product.id,
                'name'              : cart_list[i].product.name,
                'price'             : cart_list[i].product.price,
                'discount_rate'     : cart_list[i].product.discount_rate.discount_rate,
                'quantity'          : cart_list[i].quantity,
                'thumbnail_image'   : cart_list[i].product.thumbnail_image
            } for i in range(len(cart_list))] if cart_list else None
        }]
        return JsonResponse({'result' : result}, status=200)

    @login_required
    def post(self, request):
        try:
            data               = json.loads(request.body)
            product_id         = data['product_id']
            shipping_method_id = data['shipping_method_id']
            quantity           = data['quantity']
            
            if not (product_id and shipping_method_id and quantity):
                return JsonResponse({'message':'Empty Data'}, status=400)
            
            user               = request.user
            product            = Product.objects.filter(id=product_id).first() 
            shipping_method    = ShippingMethod.objects.filter(id=shipping_method_id).first()
    
            if not product:
                return JsonResponse({'message':'UNKOWN_PRODUCT'}, status=400)

            if not shipping_method:
                return JsonResponse({'message':'INVALID_Shipping_Method'}, status=400)

            if OrderStatus.objects.filter(id=1):
                with transaction.atomic():
                    order, is_created              = Order.objects.get_or_create(
                        user_id=user.id, order_status_id=1
                    )
                
                    cart, is_created               = Cart.objects.get_or_create(
                        order=order, product=product
                    )

                    if not is_created:
                        cart.quantity             += quantity
                        cart.order.total_quantity += cart.quantity
                        cart.order.total_price    += cart.product.price * cart.quantity
                    else:
                        cart.quantity              = quantity
                        cart.order.total_quantity  = cart.quantity
                        cart.order.total_price     = cart.product.price * cart.quantity
                        cart.order.shipping_method = shipping_method
                        cart.order.shipping_price  = 3500
            
                    order.save()
                    cart.save()
            else:
                return JsonResponse({'message':'INPUT_Order_Status Data'}, status=400)

        except KeyError:
            return JsonResponse({'message':'KEY_ERROR'}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'message':'JSON_Decode_Error'}, status=400)
        
        return JsonResponse({'message' : 'SUCCESS'}, status=201)

class BasketAddressView(View):
    @login_required
    def get(self, request):
        user    = request.user
        
        result  = [{
            'address' : Address.objects.filter(
                Q(user_id=user.id) & Q(is_default=True)).first().address
        }]
        return JsonResponse({'result' : result}, status=200)

class BasketQuantityView(View):
    @login_required
    def post(self, request):
        try:
            data               = json.loads(request.body)
            user               = request.user
            product_id         = data['product_id']
            add                = data['is_add']

            if not product_id:
                return JsonResponse({'message':'INPUT product_id'}, status=400)

            if add is None or type(add) == type('string'):
                return JsonResponse({'message':'INPUT ADD OR DECRESE'}, status=400)

            order              = Order.objects.filter(user_id=user.id).first()
            cart               = order.cart_set.filter(product_id=product_id).first() if order else None

            if not order:
                return JsonResponse({'message':'UNVALID ORDER'}, status=400)
            
            if not cart:
                return JsonResponse({'message':'EMPTY CART'}, status=400)

            with transaction.atomic():

                cart.quantity              = cart.quantity + 1 if add else cart.quantity-1

                cart.save()               

                cart.order.total_quantity  = cart.order.totla_quantity + 1 if add else cart.order.total_quantity - 1
                cart.order.total_price     = cart.order.total_price + cart.product.price if add else cart.order.total_price -cart.product.price

                cart.order.save()

        except KeyError:
            return JsonResponse({'message':'KEY_ERROR'}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'message':'JSON_Decode_Error'}, status=400)
 
        return JsonResponse({'message':'SUCCESS'}, status=201)

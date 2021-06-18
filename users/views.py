import bcrypt
import jwt
import my_settings
import json
import string
import random

from django.db        import transaction
from django.views     import View
from django.http      import JsonResponse
from django.db.models import Q
from django.core.mail import EmailMessage

from users.models     import User, Address, Review, UserLike, Comment
from products.models  import (
    Product,Category,
    SubCategory,Allergy,
    ProductInformation,AllergyProduct,
    DiscountRate,Sticker)
from users.decorators import login_required


class FindIdView(View):
    def post(self, request):

        try:
            data  = json.loads(request.body)
            name  = data['name']
            email = data['email']

            if not my_settings.EMAIL_CHECK.match(email):
                return JsonResponse({'MESSAGE': 'EMAIL_TYPE_ERROR'}, status=400)

            if not User.objects.filter(Q(name=name) & Q(email=email)).exists():
                return JsonResponse({'MESSAGE': 'INVALID_EMAIL_OR_INVALID_NAME'}, status=400)

            user = User.objects.get(email=email)

            return JsonResponse({'MESSAGE': user.identification}, status=200)

        except KeyError:
            return JsonResponse({'MESSAGE': 'KEY_ERROR'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'MESSAGE': 'JSON_Decode_Error'}, status=400)


class UserView(View):
    def post(self, request):
        try:
            data           = json.loads(request.body)
            LENGTH         = 0
            identification = data['id']
            password       = data['password']
            name           = data['name']
            email          = data['email']
            phone_number   = data['phone_number']
            birth_date     = data['birthdate']
            gender         = data['gender']
            address        = data['address']

            if len(name) <= LENGTH:
                return JsonResponse({'MESSAGE': 'NAME_ERRROR'}, status=400)

            if len(birth_date) <= LENGTH:
                return JsonResponse({'MESSAGE': 'BIRTHDATE_ERRROR'}, status=400)

            if len(gender) <= LENGTH:
                return JsonResponse({'MESSAGE': 'GENDER_ERRROR'}, status=400)

            if len(address) <= LENGTH:
                return JsonResponse({'MESSAGE': 'ADDRESS_INPUT_ERROR'}, status=400)

            if not my_settings.identification_check.match(identification):
                return JsonResponse({'MESSAGE': 'INVALID_ID_ERROR'}, status=400)

            if not my_settings.password_check.match(password):
                return JsonResponse({'MESSAGE': 'INVALID_PW_ERROR'}, status=400)

            if not my_settings.email_check.match(email):
                return JsonResponse({'MESSAGE': 'INVALID_EMAIL_ERROR'}, status=400)

            if not my_settings.phone_check.match(phone_number):
                return JsonResponse({'MESSAGE': 'INVALID_PHONENUMBER'}, status=400)

            if User.objects.filter(identification=identification).exists():
                return JsonResponse({'MESSAGE': 'ID_DUPLICATE_ERROR'}, status=400)

            if User.objects.filter(phone_number=phone_number).exists():
                return JsonResponse({'MESSSAGE': 'PHONE_NUMBER_DUPLICATE_ERROR'}, status=400)

            if User.objects.filter(email=email).exists():
                return JsonResponse({'MESSSAGE': 'EMAIL_DUPLICATE_ERROR'}, status=401)

            with transaction.atomic():
                hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                user      = User.objects.create(
                    identification = identification,
                    password       = hashed_pw.decode('utf-8'),
                    name           = name,
                    email          = email,
                    phone_number   = phone_number,
                    birthdate      = birth_date,
                    gender         = gender)

                user_address = Address.objects.create(
                    address    = address,
                    user       = user,
                    is_default = data['is_defalut'])

                user_address.save()

                return JsonResponse({'MESSAGE': 'SUCCESS'}, status=201)

        except KeyError:
            return JsonResponse({'MESSAGE': 'KEY_ERROR'}, status=400)

class FindPasswordView(View):
    def random_choices(self):
        length      = 8
        string_pool = string.ascii_letters + string.digits
        auth_num    = ''

        for i in range(length):
            auth_num += random.choice(string_pool)

        return auth_num

    def post(self, request):
        data     = json.loads(request.body)
        auth_num = self.random_choices()

        try:
            name           = data['name']
            identification = data['identification']
            email          = data['email']

            if not User.objects.filter(Q(name=name) & Q(identification=identification) & Q(email=email)).exists():
                return JsonResponse({'MESSAGE':'INVALID_USER'}, status=400)

            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(auth_num.encode('utf-8'), salt)
            hashed_password = hashed_password.decode('utf-8')

            user = User.objects.get(email=email)
            user.password = hashed_password
            user.save()

            email = EmailMessage('[CHOKURLY] 이메일 인증번호', auth_num, to=[email])
            email.send()

            return JsonResponse({'MESSAGE':'SUCCESS'}, status=200)

        except KeyError:
            return JsonResponse({'MESSAGE':'KEY_ERROR'}, status=400)

class LoginView(View):
    def post(self, request):
        try:
            data                 =  json.loads(request.body)
            password             =  data['password']
            identification       =  User.objects.filter(identification = data['id']).first()
            
            if not identification:
                return JsonResponse({'MESSAGE':'INVALID_ID_ERROR'}, status=401)
        
            if not bcrypt.checkpw(password.encode('utf-8'), identification.password.encode('utf-8') ):
                return JsonResponse({'MESSAGE':'INVALID_PW_ERROR'}, status=401)
            
            encoded_jwt = jwt.encode({'user id': identification.id}, my_settings.SECRET['secret'], algorithm = 'HS256')
            return JsonResponse({'MESSAGE':'SUCCESS','TOKEN': encoded_jwt}, status = 200)

        except KeyError:
            return JsonResponse({'MESSAGE':'KEY_ERROR'}, status=400)

class SignupCheckView(View):
    def post(self, request):
        try:
            data                = json.loads(request.body)
            email               = data.get('email','')
            identification      = data.get('id','')

            if not User.objects.filter(Q(identification = identification)| Q(email = email)).exists():
                return JsonResponse({'MESSAGE':True}, status = 200)
                
            return JsonResponse({'MESSAGE':False}, status = 200)

        except KeyError:
            return JsonResponse({'MESSAGE':'KEY_ERROR'}, status=400)

class ReviewView(View):
    @login_required
    def post(self,request,product_id=None):
        result = False

        try:
            data   = json.loads(request.body)
            review = data['review']
            user   = request.user
            orders = user.order_set.filter(order_status_id = 3)

            if not product_id or not Product.objects.filter(id=product_id).exists():
                return JsonResponse({'MESSAGE':'PRODUCT_DOES_NOT_EXIST'},status = 400)

            if not review:
                return JsonResponse({'MESSAGE':'INVALID_REVIEW'},status = 400)

            if not orders:
                return JsonResponse({'MESSAGE':'INVALID_USER'},status = 400)

            for order in orders:
                if order.cart_set.filter(product_id=product_id).exists():
                    result = True
                    break

            if not result:
                return JsonResponse({'MESSAGE':'INVALID_USER'}, status = 400)

            Review.objects.create(
                user   = user,
                review = review,
                order  = order
            )

            return JsonResponse({'MESSAGE':'SUCCESS'},status = 201)

        except json.JSONDecodeError:
            return JsonResponse({'MESSAGE':'JSON_DECODE_ERROR'}, status = 400)

        except KeyError:
            return JsonResponse({'MESSAGE': 'KEY_ERROR'}, status = 400)

    def get(self,request,product_id=None):

        if not product_id or not Product.objects.filter(id=product_id).exists():
            return JsonResponse({'MESSAGE': 'PRODUCT_DOES_NOT_EXIST'}, status = 400)

        reviews = Review.objects.filter(product_id = product_id)

        results = [
            {
                'ID'         : review.user.identification,
                'created_at' : review.created_at.strftime('%Y-%m-%d'),
                'review'     : review.review

            } for review in reviews]

        return JsonResponse({'RESULTS':results}, status = 200)

    @login_required
    def delete(self,request,product_id = None):

        try:
            if not product_id or not Product.objects.filter(id=product_id).exists():
                return JsonResponse({'MESSAGE': 'PRODUCT_DOES_NOT_EXIST'}, status = 400)

            data         = json.loads(request.body)
            review_id    = data['review_id']
            user         = request.user
            review_check = Review.objects.filter(id=review_id, user=user).exists()

            if not review_check:
                return JsonResponse({'MESSAGE':'INVALID_REQUEST'}, status = 400)

            Review.objects.filter(id=review_id, user=user).delete()

            return JsonResponse({'MESSAGE': 'SUCCESS'}, status = 200)

        except json.JSONDecodeError:
            return JsonResponse({'MESSAGE':'JSON_DECODE_ERROR'}, status = 400)

class UserLikeView(View):
    @login_required
    def get(self,request):
        product_id = request.GET.get('product_id')

        if not product_id:
            return JsonResponse({'MESSAGE':'INVALID_PRODUCT_ID'}, status = 400)

        user = request.user
        like, like_check = UserLike.objects.get_or_create(user = user,product = product_id)

        if not like_check:
            if like.is_like:
                like.is_like = False
            else:
                like.is_like = True

        like.save()
        total = UserLike.objects.filter(product = product_id, is_like = True).count()

        return JsonResponse({'RESULTS': total}, status = 200)

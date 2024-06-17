from django.http import  JsonResponse
from django.shortcuts import redirect, render
from finalapp.form import CustomUserForm
from . models import *
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout

import json
import logging

logger = logging.getLogger(__name__)
 # views.py
import razorpay
from django.conf import settings
from django.shortcuts import render, redirect
from .models import Cart, Order, OrderItem
# views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.db.models import F,Sum
 
from django.db import transaction

@csrf_exempt
def verify_payment(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            logger.debug("Payment data received: %s", data)
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

            # Verify the payment signature
            client.utility.verify_payment_signature(data)

            # Fetch payment details
            razorpay_payment_id = data['razorpay_payment_id']
            razorpay_order_id = data['razorpay_order_id']

            # Fetch the order using the razorpay_order_id
            order = Order.objects.get(razorpay_order_id=razorpay_order_id)
            logger.debug("Order found: %s", order)

            # Update the order as paid
            order.is_paid = True
            order.razorpay_payment_id = razorpay_payment_id
            order.save()
            logger.debug("Order updated as paid: %s", order)

            # Create OrderItems from the Cart items
            cart_items = Cart.objects.filter(user=order.user)
            if not cart_items.exists():
                logger.error("No cart items found for user %s", order.user)

            for item in cart_items:
                try:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        quantity=item.product_qty,
                        price=item.product.selling_price,
                        total=item.total_cost
                    )
                    logger.debug("OrderItem created for cart item: %s", item)
                except Exception as e:
                    logger.error("Error creating OrderItem for cart item %s: %s", item, e)
                    raise

            # Clear the cart after creating OrderItems
            cart_items.delete()
            logger.debug("Cart items deleted for user: %s", order.user)

            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error("Error in verify_payment: %s", e)
            return JsonResponse({'status': 'failure', 'error': str(e)}, status=400)
    else:
        return HttpResponse(status=405)

def create_order(request):
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user)
        total_amount = cart_items.aggregate(total_amount=Sum(F('product_qty') * F('product__selling_price')))['total_amount']

        if total_amount is None:
            total_amount = 0

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        razorpay_order = client.order.create({
            'amount': int(total_amount * 100),  # amount in paise
            'currency': 'INR',
            'payment_capture': '1'
        })

        order = Order.objects.create(
            user=request.user,
            razorpay_order_id=razorpay_order['id'],
            total_amount=total_amount
        )

        context = {
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'total_amount': total_amount,
            'order': order,
        }
        return render(request, 'shop/cart.html', context)
    else:
        return redirect('login')

 
def home(request):
  products=Product.objects.filter(trending=1)
  return render(request,"shop/index.html",{"products":products})
 
def favviewpage(request):
  if request.user.is_authenticated:
    fav=Favourite.objects.filter(user=request.user)
    return render(request,"shop/fav.html",{"fav":fav})
  else:
    return redirect("/")
 
def remove_fav(request,fid):
  item=Favourite.objects.get(id=fid)
  item.delete()
  return redirect("/favviewpage")
 
 
 
 
def cart_page(request):
  if request.user.is_authenticated:
    cart=Cart.objects.filter(user=request.user)
    return render(request,"shop/cart.html",{"cart":cart})
  else:
    return redirect("/")
 
def remove_cart(request,cid):
  cartitem=Cart.objects.get(id=cid)
  cartitem.delete()
  return redirect("/cart")
 
 
 
def fav_page(request):
   if request.headers.get('x-requested-with')=='XMLHttpRequest':
    if request.user.is_authenticated:
      data=json.load(request)
      product_id=data['pid']
      product_status=Product.objects.get(id=product_id)
      if product_status:
         if Favourite.objects.filter(user=request.user.id,product_id=product_id):
          return JsonResponse({'status':'Product Already in Favourite'}, status=200)
         else:
          Favourite.objects.create(user=request.user,product_id=product_id)
          return JsonResponse({'status':'Product Added to Favourite'}, status=200)
    else:
      return JsonResponse({'status':'Login to Add Favourite'}, status=200)
   else:
    return JsonResponse({'status':'Invalid Access'}, status=200)
 
 
def add_to_cart(request):
   if request.headers.get('x-requested-with')=='XMLHttpRequest':
    if request.user.is_authenticated:
      data=json.load(request)
      product_qty=data['product_qty']
      product_id=data['pid']
      #print(request.user.id)
      product_status=Product.objects.get(id=product_id)
      if product_status:
        if Cart.objects.filter(user=request.user.id,product_id=product_id):
          return JsonResponse({'status':'Product Already in Cart'}, status=200)
        else:
          if product_status.quantity>=product_qty:
            Cart.objects.create(user=request.user,product_id=product_id,product_qty=product_qty)
            return JsonResponse({'status':'Product Added to Cart'}, status=200)
          else:
            return JsonResponse({'status':'Product Stock Not Available'}, status=200)
    else:
      return JsonResponse({'status':'Login to Add Cart'}, status=200)
   else:
    return JsonResponse({'status':'Invalid Access'}, status=200)
 
def logout_page(request):
  if request.user.is_authenticated:
    logout(request)
    messages.success(request,"Logged out Successfully")
  return redirect("/")
 
 
def login_page(request):
  if request.user.is_authenticated:
    return redirect("/")
  else:
    if request.method=='POST':
      name=request.POST.get('username')
      pwd=request.POST.get('password')
      user=authenticate(request,username=name,password=pwd)
      if user is not None:
        login(request,user)
        messages.success(request,"Logged in Successfully")
        return redirect("/")
      else:
        messages.error(request,"Invalid User Name or Password")
        return redirect("/login")
    return render(request,"shop/login.html")
 
def register(request):
  form=CustomUserForm()
  if request.method=='POST':
    form=CustomUserForm(request.POST)
    if form.is_valid():
      form.save()
      messages.success(request,"Registration Success You can Login Now..!")
      return redirect('/login')
  return render(request,"shop/register.html",{'form':form})
 
 
def collections(request):
  catagory=Catagory.objects.filter(status=0)
  return render(request,"shop/collections.html",{"catagory":catagory})
 
def collectionsview(request,name):
  if(Catagory.objects.filter(name=name,status=0)):
      products=Product.objects.filter(category__name=name)
      return render(request,"shop/products/index.html",{"products":products,"category_name":name})
  else:
    messages.warning(request,"No Such Catagory Found")
    return redirect('collections')
 
 
def product_details(request,cname,pname):
    if(Catagory.objects.filter(name=cname,status=0)):
      if(Product.objects.filter(name=pname,status=0)):
        products=Product.objects.filter(name=pname,status=0).first()
        return render(request,"shop/products/product_details.html",{"products":products})
      else:
        messages.error(request,"No Such Produtct Found")
        return redirect('collections')
    else:
      messages.error(request,"No Such Catagory Found")
      return redirect('collections')
@csrf_exempt
def razorpay_callback(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            client.utility.verify_payment_signature(data)
            razorpay_payment_id = data['razorpay_payment_id']
            razorpay_order_id = data['razorpay_order_id']

            order = Order.objects.get(razorpay_order_id=razorpay_order_id)
            order.is_paid = True
            order.razorpay_payment_id = razorpay_payment_id
            order.save()

            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'failure', 'error': str(e)}, status=400)
    else:
        return HttpResponse(status=405)

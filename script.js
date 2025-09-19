
document.addEventListener('DOMContentLoaded', () => {
  // --- Existing Elements ---
  const loginView = document.getElementById('login-view');
  const customerPortal = document.getElementById('customer-portal');
  const employeePortal = document.getElementById('employee-portal');
  // ... other existing elements

  // --- New Premium Service & Payment Elements ---
  const orderDroneVideoBtn = document.getElementById('order-drone-video-btn');
  const droneVideoOrderBox = document.getElementById('drone-video-order-box');
  const droneVideoDisplayBox = document.getElementById('drone-video-display-box');
  const paymentElementContainer = document.getElementById('payment-element');
  const submitPaymentBtn = document.getElementById('submit-payment-btn');

  let currentPlotId = null;
  let stripe = null;
  let elements = null;

  // **IMPORTANT**: Replace with your actual Stripe Publishable Key
  const stripePublicKey = 'YOUR_STRIPE_PUBLISHABLE_KEY';

  // --- AUTH STATE OBSERVER ---
  auth.onAuthStateChanged(async (user) => {
    if (user) {
      // ... existing onAuthStateChanged logic ...
    } else {
      showLoginView();
    }
  });


  // --- NEW DRONE VIDEO & PAYMENT FUNCTIONS ---

  /**
   * Initiates the drone video order process by calling the cloud function.
   */
  const handleDroneOrderClick = async () => {
    if (!currentPlotId) {
      alert('Could not determine the plot ID.');
      return;
    }

    orderDroneVideoBtn.disabled = true;
    orderDroneVideoBtn.textContent = 'Processing...';

    try {
      const createDroneOrder = functions.httpsCallable('createDroneOrder');
      const result = await createDroneOrder({ plotId: currentPlotId });
      
      if (result.data.clientSecret) {
        await initializePaymentElement(result.data.clientSecret);
        droneVideoOrderBox.style.display = 'none';
        paymentElementContainer.style.display = 'block';
        submitPaymentBtn.style.display = 'block';
      } else {
        throw new Error('Could not retrieve payment information.');
      }
    } catch (error) {
      alert(`Error starting order: ${error.message}`);
      console.error('Drone order error:', error);
      orderDroneVideoBtn.disabled = false;
      orderDroneVideoBtn.textContent = 'Order Cinematic Drone Video ($299)';
    }
  };

  /**
   * Initializes and mounts the Stripe Payment Element.
   * @param {string} clientSecret The client secret from the Stripe Payment Intent.
   */
  const initializePaymentElement = async (clientSecret) => {
    stripe = Stripe(stripePublicKey);
    elements = stripe.elements({ clientSecret });

    const paymentElement = elements.create('payment');
    paymentElement.mount('#payment-element');
  };

  /**
   * Handles the submission of the payment form to Stripe.
   */
  const handlePaymentSubmit = async () => {
    if (!stripe || !elements) {
        alert('Payment system is not ready. Please try again.');
        return;
    }

    submitPaymentBtn.disabled = true;
    submitPaymentBtn.textContent = 'Processing Payment...';

    const {
        error
    } = await stripe.confirmPayment({
        elements,
        confirmParams: {
            // Make sure to change this to your payment completion page
            return_url: `${window.location.origin}?payment_success=true&plot_id=${currentPlotId}`,
        },
    });

    // This point will only be reached if there is an immediate error when
    // confirming the payment. Otherwise, your customer will be redirected to
    // the `return_url`. For some payment methods like iDEAL, your customer will
    // be redirected to an intermediate site first to authorize the payment, then
    // redirected to the `return_url`.
    if (error) {
        alert(`Payment failed: ${error.message}`);
        submitPaymentBtn.disabled = false;
        submitPaymentBtn.textContent = 'Submit Payment';
    }
  };

  /**
   * Checks for payment success URL parameters on page load.
   */
  const checkPaymentSuccess = () => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('payment_success') === 'true') {
      alert('Thank you! Your payment was successful and your order is being processed.');
      // Optionally, you can use the plot_id to automatically load that memorial
      const plotId = urlParams.get('plot_id');
      if (plotId) {
          // This assumes the user is already logged in. `onAuthStateChanged` will handle the initial load.
          // This is just to ensure the correct plot is displayed after redirect.
          loadMemorialData(plotId);
      }
    }
  };

  // --- UPGRADED `loadMemorialData` FUNCTION ---

  const loadMemorialData = async (plotId) => {
    // ... (all existing logic from the previous step for photos and stories remains here)
    
    // **NEW**: Check for existing drone video order
    try {
      const droneOrderQuery = await db.collection('drone_service_orders')
          .where('plotId', '==', plotId)
          .where('orderStatus', '==', 'completed')
          .limit(1).get();

      if (!droneOrderQuery.empty) {
          const orderData = droneOrderQuery.docs[0].data();
          if (orderData.videoUrl) {
              // A completed video exists, so display it and hide the order button
              droneVideoOrderBox.style.display = 'none';
              droneVideoDisplayBox.style.display = 'block';
              droneVideoDisplayBox.innerHTML = `
                  <h4>Your Cinematic Drone Video</h4>
                  <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden;">
                      <iframe 
                          src="${orderData.videoUrl}" 
                          style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;" 
                          frameborder="0" 
                          allow="autoplay; fullscreen; picture-in-picture" 
                          allowfullscreen>
                      </iframe>
                  </div>
              `;
          } else {
            // Order exists but is not complete yet, show a status
            droneVideoOrderBox.innerHTML = '<p>Your drone video order is currently being processed.</p>';
          }
      } else {
          // No completed order, ensure the order button is visible and ready
          droneVideoOrderBox.style.display = 'block';
          droneVideoDisplayBox.style.display = 'none';
      }
    } catch (error) {
      console.error("Error checking for drone video orders:", error);
    }
  };

  // --- Other existing functions (handleLogin, showCustomerPortal, etc.) ---
  // ...

  // --- EVENT LISTENERS ---
  // ... (existing listeners for auth and living memorial)

  // New listeners for the drone service
  orderDroneVideoBtn.addEventListener('click', handleDroneOrderClick);
  submitPaymentBtn.addEventListener('click', handlePaymentSubmit);

  // --- INITIALIZATION ---
  checkPaymentSuccess(); // Check for post-payment redirect on initial load
});

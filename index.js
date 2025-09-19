
const functions = require("firebase-functions");
const admin = require("firebase-admin");
const stripe = require("stripe")(functions.config().stripe.secret_key);
const Mux = require("@mux/mux-node");

admin.initializeApp();

// Initialize Mux with your credentials from Firebase environment configuration
const { V1 } = new Mux(functions.config().mux.token_id, functions.config().mux.token_secret);
const { Video } = V1;

// --- Existing Cloud Functions (createWorkOrder, createDroneOrder, etc.) ---
// ...

// --- NEW LIVE STREAM CLOUD FUNCTIONS ---

/**
 * Creates a live stream order, provisions a Mux live stream, and saves details to Firestore.
 *
 * @param {object} data - The data for the new order.
 * @param {string} data.plotId - The ID of the plot for the service.
 * @param {string} data.scheduledTimestamp - The ISO 8601 string of the scheduled time.
 * @returns {Promise<object>} - A promise that resolves with the new order's ID.
 */
exports.createLiveStreamOrder = functions.https.onCall(async (data, context) => {
  // 1. Authentication and Validation
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "You must be logged in to order.");
  }
  const { plotId, scheduledTimestamp } = data;
  if (!plotId || !scheduledTimestamp) {
    throw new functions.https.HttpsError("invalid-argument", "Missing plotId or scheduledTimestamp.");
  }

  try {
    // 2. Create a new Live Stream in Mux
    const liveStream = await Video.LiveStreams.create({
      playback_policy: ['public'],
      new_asset_settings: {
        playback_policy: ['public'],
        mp4_support: 'standard' // To have a downloadable archive
      },
      reconnect_window: 60
    });

    // 3. Create the order document in Firestore
    const orderData = {
      plotId: plotId,
      customerId: context.auth.uid,
      orderStatus: "scheduled",
      scheduledTime: admin.firestore.Timestamp.fromDate(new Date(scheduledTimestamp)),
      muxLiveStreamId: liveStream.id,
      muxStreamKey: liveStream.stream_key,
      muxPlaybackId: liveStream.playback_ids[0].id,
      archiveUrl: null, // This will be populated later
    };

    const orderRef = await admin.firestore().collection("live_stream_orders").add(orderData);

    // 4. Return the new order ID
    return { orderId: orderRef.id };

  } catch (error) {
    console.error("Error creating live stream order:", error);
    throw new functions.https.HttpsError("internal", "An error occurred while creating the live stream.");
  }
});

/**
 * [Admin-Only] Updates the status of a live stream order.
 *
 * @param {object} data - The data for the update.
 * @param {string} data.orderId - The ID of the live_stream_orders document.
 * @param {string} data.newStatus - The new status (e.g., 'live', 'completed').
 * @returns {Promise<object>} - A promise that resolves with a success message.
 */
exports.updateStreamStatus = functions.https.onCall(async (data, context) => {
  // 1. Authentication & Authorization
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "Authentication required.");
  }
  const userDoc = await admin.firestore().collection('users').doc(context.auth.uid).get();
  if (!userDoc.exists || userDoc.data().role !== 'employee') {
      throw new functions.https.HttpsError("permission-denied", "You must be an employee to perform this action.");
  }

  const { orderId, newStatus } = data;
  if (!orderId || !newStatus) {
    throw new functions.https.HttpsError("invalid-argument", "Missing orderId or newStatus.");
  }

  try {
    const orderRef = admin.firestore().collection("live_stream_orders").doc(orderId);
    await orderRef.update({ orderStatus: newStatus });
    
    // Optional: If completing, you might fetch the archive URL from Mux
    // This is a simplified approach. A webhook from Mux is the robust solution.
    if (newStatus === 'completed') {
        const orderDoc = await orderRef.get();
        const muxLiveStreamId = orderDoc.data().muxLiveStreamId;
        // Mux assets are created from the live stream. We can find the one associated.
        const assets = await Video.Assets.list({ live_stream_id: muxLiveStreamId });
        if (assets && assets.length > 0 && assets[0].playback_ids) {
            const playbackId = assets[0].playback_ids[0].id;
            const archiveUrl = `https://stream.mux.com/${playbackId}.m3u8`;
            await orderRef.update({ archiveUrl: archiveUrl });
        }
    }

    return { success: true, message: `Order ${orderId} status updated to ${newStatus}.` };

  } catch (error) {
    console.error("Error updating stream status:", error);
    throw new functions.https.HttpsError("internal", "Could not update stream status.");
  }
});

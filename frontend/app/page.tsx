"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Phone, PhoneOff, User, Eye, CheckCircle2, AlertCircle, 
  Radio, MessageSquare, ShieldAlert, FileText, Sparkles, Clock, Calendar, CheckSquare, RefreshCw
} from "lucide-react";
import { Room, RoomEvent } from "livekit-client";

const defaultSessionState = {
  room_name: "",
  caller_name: "",
  reason: "",
  preferred_date_time: "",
  contact_number: "",
  is_booked: false,
  call_status: "connected",
  agent_state: "listening",
  detected_intent: "None",
  current_action: "None",
  transcript: [] as { speaker: string; text: string; timestamp?: number }[],
  transfer_status: "idle",
  post_call_summary: "",
  takeover_active: false,
};

const normalizeSessionState = (data: any) => ({
  ...defaultSessionState,
  ...data,
  transcript: Array.isArray(data?.transcript) ? data.transcript : defaultSessionState.transcript,
  room_name: data?.room_name ?? defaultSessionState.room_name,
});

export default function Home() {
  // Configuration
  const [backendUrl, setBackendUrl] = useState("");
  const [roomName, setRoomName] = useState("dental-clinic-session-1");
  const [identity, setIdentity] = useState("");
  const [role, setRole] = useState<"caller" | "watcher" | null>(null);
  const [livekitUrl, setLivekitUrl] = useState("wss://shweta-hackathon-pgyvofsu.livekit.cloud");

  // Live Syncing Session State (now received instantly over WebSockets!)
  const [sessionState, setSessionState] = useState({
    room_name: "",
    caller_name: "",
    reason: "",
    preferred_date_time: "",
    contact_number: "",
    is_booked: false,
    call_status: "connected", // connected -> transferring -> ended
    agent_state: "listening", // listening -> thinking -> speaking -> monitoring
    detected_intent: "None",
    current_action: "None",
    transcript: [] as { speaker: string; text: string; timestamp?: number }[],
    transfer_status: "idle",  // idle -> calling -> accepted -> declined
    post_call_summary: "",
    takeover_active: false
  });

  // Connection State
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [lkRoom, setLkRoom] = useState<Room | null>(null);

  // Local Watcher/Supervisor Takeover Microphone State
  const [isLocalMicMuted, setIsLocalMicMuted] = useState(true);
  
  // Simulator States
  const [simulatedText, setSimulatedText] = useState("");
  const [isSimulating, setIsSimulating] = useState(false);

  // Caller Chat State
  const [callerChatText, setCallerChatText] = useState("");

  // Browser Speech-to-Text (Voice Recognition) States
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  // Editable form fields for the Supervisor/Watcher
  const [editableName, setEditableName] = useState("");
  const [editablePhone, setEditablePhone] = useState("");
  const [editableReason, setEditableReason] = useState("");
  const [editableTime, setEditableTime] = useState("");

  // Sync with sessionState updates
  useEffect(() => {
    if (sessionState) {
      setEditableName(sessionState.caller_name || "");
      setEditablePhone(sessionState.contact_number || "");
      setEditableReason(sessionState.reason || "");
      setEditableTime(sessionState.preferred_date_time || "");
    }
  }, [sessionState.caller_name, sessionState.contact_number, sessionState.reason, sessionState.preferred_date_time]);

  const handleManualBook = async () => {
    if (!editableName || !editableTime) {
      alert("Please fill in both the Caller Name and Preferred Date/Time.");
      return;
    }
    try {
      const res = await fetch(`${backendUrl}/api/v1/session/${roomName}/book`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          caller_name: editableName,
          contact_number: editablePhone,
          reason: editableReason,
          preferred_date_time: editableTime
        })
      });
      if (res.ok) {
        const data = await res.json();
        setSessionState(normalizeSessionState(data));
        alert("Appointment successfully registered in local MySQL database!");
      }
    } catch (e) {
      console.error("Error manual booking:", e);
    }
  };

  const handleCallerSendChat = async () => {
    if (!callerChatText || !callerChatText.trim()) return;
    try {
      const res = await fetch(`${backendUrl}/api/v1/session/${roomName}/event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript_item: {
            speaker: "caller",
            text: callerChatText,
            timestamp: Date.now() / 1000
          }
        })
      });
      if (res.ok) {
        // Also send WebRTC Room Data Message to trigger real-time AI reply
        if (lkRoom) {
          try {
            const dataEncoder = new TextEncoder();
            const payload = dataEncoder.encode(JSON.stringify({ type: "chat", text: callerChatText }));
            await lkRoom.localParticipant.publishData(payload, { reliable: true });
            console.log("⚡ Sent chat WebRTC data message to room");
          } catch (err) {
            console.error("Failed to publish WebRTC room chat:", err);
          }
        }
        setCallerChatText("");
        const data = await res.json();
        setSessionState(normalizeSessionState(data));
      }
    } catch (e) {
      console.error("Error sending caller chat:", e);
    }
  };

  const handleCallerSendChatDirectly = async (textToSend: string) => {
    if (!textToSend || !textToSend.trim()) return;
    try {
      const res = await fetch(`${backendUrl}/api/v1/session/${roomName}/event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript_item: {
            speaker: "caller",
            text: textToSend,
            timestamp: Date.now() / 1000
          }
        })
      });
      if (res.ok) {
        if (lkRoom) {
          try {
            const dataEncoder = new TextEncoder();
            const payload = dataEncoder.encode(JSON.stringify({ type: "chat", text: textToSend }));
            await lkRoom.localParticipant.publishData(payload, { reliable: true });
            console.log("⚡ Sent simulated WebRTC chat over room data track");
          } catch (err) {
            console.error("Failed to publish WebRTC room chat:", err);
          }
        }
        const data = await res.json();
        setSessionState(normalizeSessionState(data));
      }
    } catch (e) {
      console.error("Error sending direct caller chat:", e);
    }
  };

  const startSpeechRecognition = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Browser speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.");
      return;
    }

    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = "en-US";

    rec.onstart = () => {
      setIsListening(true);
      console.log("🎤 Browser speech recognition started...");
    };

    rec.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      console.log("🎤 Speech recognition result:", transcript);
      setCallerChatText(transcript);
      handleCallerSendChatDirectly(transcript);
    };

    rec.onerror = (err: any) => {
      console.error("🎤 Speech recognition error:", err);
      setIsListening(false);
    };

    rec.onend = () => {
      setIsListening(false);
      console.log("🎤 Speech recognition ended.");
    };

    recognitionRef.current = rec;
    rec.start();
  };

  const handleSimulateSpeech = async (textToSend: string) => {
    if (!textToSend || !textToSend.trim()) return;
    setIsSimulating(true);
    try {
      const res = await fetch(`${backendUrl}/api/v1/session/${roomName}/event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript_item: {
            speaker: "caller",
            text: textToSend,
            timestamp: Date.now() / 1000
          }
        })
      });
      if (res.ok) {
        setSimulatedText("");
      }
    } catch (e) {
      console.error("Error sending simulated speech:", e);
    } finally {
      setIsSimulating(false);
    }
  };

  // Refs for tracking elements
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Automatically scroll transcript to bottom
  useEffect(() => {
    if (!sessionState?.transcript || !transcriptEndRef.current) {
      return;
    }
    transcriptEndRef.current.scrollIntoView({ behavior: "smooth" });
  }, [sessionState?.transcript]);

  // Fetch LiveKit Server configuration dynamically from FastAPI backend on load
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const res = await fetch(`${backendUrl}/api/v1/config`);
        if (res.ok) {
          const data = await res.json();
          if (data.livekit_url) {
            setLivekitUrl(data.livekit_url);
            console.log("🚀 Loaded LiveKit Server URL dynamically from backend settings:", data.livekit_url);
          }
        }
      } catch (e) {
        console.error("Error fetching config from backend:", e);
      }
    };
    fetchConfig();
  }, [backendUrl]);

  // Connect to FastAPI WebSockets for instantaneous event broadcasting
  useEffect(() => {
    if (isConnected && role === "watcher" && roomName) {
      const wsProtocol = window.location.protocol === "https:" ? "wss://" : "ws://";
      const host = backendUrl 
        ? backendUrl.replace("http://", "").replace("https://", "") 
        : "localhost:8000";
      const wsUrl = `${wsProtocol}${host}/api/v1/ws/monitor/${roomName}`;

      console.log("🔌 Connecting to Event Broadcast WebSocket:", wsUrl);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("⚡ Real-time broadcast event received:", data);
          setSessionState(normalizeSessionState(data));
        } catch (e) {
          console.error("Error decoding broadcast event:", e);
        }
      };

      ws.onclose = () => {
        console.log("🔌 Broadcast WebSocket connection closed.");
      };

      return () => {
        ws.close();
      };
    }
  }, [isConnected, role, roomName, backendUrl]);

  // Handle Joining Room (WebRTC)
  const handleJoin = async (selectedRole: "caller" | "watcher") => {
    if (!roomName) {
      alert("Please enter a room name.");
      return;
    }
    
    setIsConnecting(true);
    setRole(selectedRole);

    const userIdent = selectedRole === "caller" ? `caller-${Math.floor(Math.random() * 1000)}` : `watcher-${Math.floor(Math.random() * 1000)}`;
    const userDisplay = selectedRole === "caller" ? "Patient (Caller)" : "Supervisor (Watcher)";
    setIdentity(userIdent);

    try {
      // 1. Fetch JWT token from FastAPI backend
      const res = await fetch(`${backendUrl}/api/v1/token?room=${roomName}&identity=${userIdent}&name=${encodeURIComponent(userDisplay)}`);
      if (!res.ok) {
        throw new Error("Failed to retrieve token from backend.");
      }
      const { token } = await res.json();

      // 2. Initialize LiveKit WebRTC client
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });

      room.on(RoomEvent.Disconnected, () => {
        setIsConnected(false);
        setRole(null);
        setLkRoom(null);
      });

      // Connect to LiveKit Room
      await room.connect(livekitUrl, token);
      console.log("✅ Successfully connected to LiveKit WebRTC room:", roomName);

      // If caller, publish microphone track
      if (selectedRole === "caller") {
        await room.localParticipant.setMicrophoneEnabled(true);
        console.log("🎤 Caller microphone enabled and streaming");
      } else {
        // Watcher joins MUTED by default
        await room.localParticipant.setMicrophoneEnabled(false);
        setIsLocalMicMuted(true);
        console.log("👁️ Watcher joined with microphone muted");
      }

      setLkRoom(room);
      setIsConnected(true);
      
    } catch (e: any) {
      console.error("WebRTC room connection failed:", e);
      alert(`Could not connect to LiveKit WebRTC Room: ${e.message || e}. Ensure your credentials are set correctly.`);
    } finally {
      setIsConnecting(false);
    }
  };

  // Handle Supervisor/Watcher Microphone Mute/Unmute (Takeover)
  const toggleLocalMic = async () => {
    if (!lkRoom) return;
    try {
      const targetMuteState = !isLocalMicMuted; // True if we want to mute, False if we want to unmute
      // Enable microphone is the opposite of mute!
      await lkRoom.localParticipant.setMicrophoneEnabled(!targetMuteState);
      setIsLocalMicMuted(targetMuteState);
      console.log(`Watcher microphone state changed: Muted = ${targetMuteState}`);
    } catch (e) {
      console.error("Error toggling microphone:", e);
    }
  };

  // Handle Supervisor Takeover (Mute Agent A, Unmute Watcher)
  const handleTakeover = async () => {
    if (!lkRoom || !isConnected) return;
    
    try {
      // 1. Send data message "take_over" to room over WebRTC (notifies Agent to mute and stop LLM)
      const dataEncoder = new TextEncoder();
      const payload = dataEncoder.encode(JSON.stringify({ type: "take_over" }));
      await lkRoom.localParticipant.publishData(payload, { reliable: true });
      console.log("Sent takeover data message to LiveKit room");

      // 2. Notify FastAPI backend to update session state in DB
      const res = await fetch(`${backendUrl}/api/v1/session/${roomName}/takeover`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        setSessionState(normalizeSessionState(data));
      }

      // 3. Unmute Watcher's microphone so they can talk directly to the caller!
      await lkRoom.localParticipant.setMicrophoneEnabled(true);
      setIsLocalMicMuted(false);
      console.log("Watcher microphone unmuted. Takeover complete!");

    } catch (e) {
      console.error("Takeover failed:", e);
    }
  };

  // Handle Warm Transfer Simulation
  const handleSimulateTransfer = async (decision: "accept" | "decline") => {
    try {
      const res = await fetch(`${backendUrl}/api/v1/session/${roomName}/simulate-transfer?decision=${decision}`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        setSessionState(normalizeSessionState(data));
      }
    } catch (e) {
      console.error("Error simulating transfer decision:", e);
    }
  };

  // Handle Disconnecting
  const handleDisconnect = async () => {
    if (lkRoom) {
      await lkRoom.disconnect();
    }
    setIsConnected(false);
    setRole(null);
    setLkRoom(null);
    
    // Update call status to ended on backend
    try {
      await fetch(`${backendUrl}/api/v1/session/${roomName}/event`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ call_status: "ended", current_action: "Call ended by user" })
      });
    } catch (e) {
      console.error("Error updating ended call status on backend:", e);
    }
  };

  // Helper to determine the call timeline events
  const getTimelineEvents = () => {
    const events = [];
    if (sessionState.room_name) {
      events.push({ title: "Call Connected", desc: "Caller entered room", time: "0:00", active: true });
    }
    if (sessionState.caller_name) {
      events.push({ title: "Name Verified", desc: `Identity: ${sessionState.caller_name}`, active: true });
    }
    if (sessionState.is_booked) {
      events.push({ title: "Appointment Booked", desc: `Slot: ${sessionState.preferred_date_time}`, active: true });
    }
    if (sessionState.takeover_active) {
      events.push({ title: "Supervisor Takeover", desc: "Watcher speaking directly", active: true });
    }
    if (sessionState.transfer_status === "accepted") {
      events.push({ title: "Human Connected", desc: "Twilio bridge complete", active: true });
    }
    if (sessionState.call_status === "ended") {
      events.push({ title: "Call Concluded", desc: "Session summarized", active: true });
    }
    return events;
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-teal-500 selection:text-black">
      {/* Top Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-md px-6 py-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-tr from-teal-500 to-emerald-400 p-2 rounded-xl text-black shadow-lg shadow-teal-500/10">
            <Radio className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-tight bg-gradient-to-r from-teal-400 to-emerald-300 bg-clip-text text-transparent">
              OpenVoice Live Console
            </h1>
            <p className="text-xs text-zinc-400 font-medium">Production-Grade AI Receptionist with WebSockets</p>
          </div>
        </div>
        
        {isConnected && (
          <div className="flex items-center gap-2 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-full text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            Active Session: {roomName}
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 flex flex-col gap-6">
        
        {/* Setup & Join Box (Before connection is active) */}
        {!isConnected ? (
          <div className="max-w-xl mx-auto w-full mt-12 bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl shadow-black/40">
            <div className="text-center mb-8">
              <Sparkles className="w-10 h-10 mx-auto text-teal-400 mb-2" />
              <h2 className="text-2xl font-bold tracking-tight">Connect to a Voice Session</h2>
              <p className="text-sm text-zinc-400 mt-1">Join as a Caller to talk to Agent A, or Watcher to monitor live.</p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                  LiveKit Server URL
                </label>
                <input
                  type="text"
                  placeholder="e.g. wss://shweta.livekit.cloud"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-teal-500 transition-colors"
                  value={livekitUrl}
                  onChange={(e) => setLivekitUrl(e.target.value)}
                />
                <p className="text-[10px] text-zinc-500 mt-1">Loaded automatically from backend (.env configuration)</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                  Backend API URL
                </label>
                <input
                  type="text"
                  placeholder="http://localhost:8000 (Default)"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-teal-500 transition-colors"
                  value={backendUrl}
                  onChange={(e) => setBackendUrl(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                  Room Name
                </label>
                <input
                  type="text"
                  placeholder="dental-clinic-session-1"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-teal-500 transition-colors"
                  value={roomName}
                  onChange={(e) => setRoomName(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4">
                <button
                  onClick={() => handleJoin("caller")}
                  disabled={isConnecting}
                  className="flex items-center justify-center gap-2 bg-gradient-to-r from-teal-500 to-emerald-500 hover:from-teal-600 hover:to-emerald-600 text-black font-bold py-3.5 px-4 rounded-xl transition-all shadow-lg hover:shadow-teal-500/10 disabled:opacity-50"
                >
                  <Phone className="w-4 h-4" />
                  {isConnecting && role === "caller" ? "Connecting..." : "Join as Caller"}
                </button>
                <button
                  onClick={() => handleJoin("watcher")}
                  disabled={isConnecting}
                  className="flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 font-bold py-3.5 px-4 rounded-xl border border-zinc-700 transition-all disabled:opacity-50"
                >
                  <Eye className="w-4 h-4" />
                  {isConnecting && role === "watcher" ? "Connecting..." : "Join as Watcher"}
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* Active Call Console */
          <div className="flex flex-col gap-6">
            
            {/* Caller View Panel */}
            {role === "caller" && (
              <div className="bg-zinc-900/30 border border-zinc-800 rounded-2xl p-8 max-w-xl mx-auto w-full text-center flex flex-col items-center gap-6 shadow-xl">
                <div className="bg-gradient-to-tr from-teal-500/10 to-emerald-400/10 border border-teal-500/20 p-6 rounded-full relative">
                  <Phone className="w-16 h-16 text-teal-400 animate-pulse" />
                  <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-emerald-500 border border-zinc-900 animate-ping"></span>
                </div>

                <div>
                  <h3 className="text-xl font-bold">Connected to Dental Receptionist</h3>
                  <p className="text-zinc-400 text-sm mt-1">Agent A is holding a natural voice conversation with you.</p>
                </div>

                {/* Pulsing indicator based on agent state */}
                <div className="flex items-center gap-2 bg-zinc-950 px-4 py-2 rounded-full border border-zinc-800">
                  <span className={`w-2 h-2 rounded-full ${
                    sessionState.agent_state === "speaking" ? "bg-blue-400 animate-pulse" :
                    sessionState.agent_state === "thinking" ? "bg-amber-400 animate-pulse" :
                    "bg-emerald-400 animate-pulse"
                  }`}></span>
                  <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Agent State: {sessionState.agent_state}
                  </span>
                </div>

                {/* Caller Text Chat Fallback */}
                <div className="w-full bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-3 mt-2 text-left">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase block tracking-wider">
                    💬 Fallback Conversation Chat (Type to talk if voice is muted!)
                  </span>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Type a message to the receptionist..."
                      className="flex-1 bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-teal-500 text-zinc-100"
                      value={callerChatText}
                      onChange={(e) => setCallerChatText(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleCallerSendChat()}
                    />
                    <button
                      onClick={startSpeechRecognition}
                      className={`font-bold px-4 py-2 rounded-xl text-xs transition-all flex items-center gap-1.5 shadow-lg ${
                        isListening 
                          ? "bg-rose-600 animate-pulse text-white shadow-rose-600/10" 
                          : "bg-zinc-800 text-zinc-200 border border-zinc-700 hover:bg-zinc-700 shadow-zinc-800/10"
                      }`}
                      title="Speak using Voice-to-Text"
                    >
                      <Radio className={`w-3.5 h-3.5 ${isListening ? "animate-spin" : ""}`} />
                      {isListening ? "Listening..." : "Speak"}
                    </button>
                    <button
                      onClick={handleCallerSendChat}
                      className="bg-teal-500 hover:bg-teal-600 text-black font-bold px-4 py-2 rounded-xl text-xs transition-all flex items-center gap-1 shadow-lg shadow-teal-500/10"
                    >
                      Send
                    </button>
                  </div>
                </div>

                {/* Caller Live Transcript List */}
                <div className="w-full bg-zinc-950 p-4 rounded-xl border border-zinc-800 text-left max-h-[150px] overflow-y-auto space-y-2.5">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase block tracking-wider">
                    📄 Live Transcript Preview
                  </span>
                  {sessionState.transcript.length === 0 ? (
                    <div className="text-zinc-600 text-xs italic">Waiting for chat conversation...</div>
                  ) : (
                    sessionState.transcript.map((item, idx) => (
                      <div key={idx} className="text-xs">
                        <span className={`font-bold uppercase tracking-wider text-[9px] mr-1 ${
                          item.speaker === "agent" ? "text-teal-400" : "text-purple-400"
                        }`}>
                          {item.speaker === "agent" ? "🤖 Agent A:" : "👤 Caller:"}
                        </span>
                        <span className="text-zinc-300">{item.text}</span>
                      </div>
                    ))
                  )}
                </div>

                <button
                  onClick={handleDisconnect}
                  className="flex items-center gap-2 bg-rose-500 hover:bg-rose-600 text-white font-bold py-3 px-6 rounded-xl transition-all shadow-lg hover:shadow-rose-500/10 mt-4"
                >
                  <PhoneOff className="w-4 h-4" />
                  End Conversation
                </button>
              </div>
            )}

            {/* Watcher (Monitoring Console) Grid Layout */}
            {role === "watcher" && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                
                {/* Left Column (Metadata, States, Controls) - 5 Cols */}
                <div className="lg:col-span-5 flex flex-col gap-6">
                  
                  {/* Card 1: Caller Details */}
                  <div className="bg-zinc-900/30 border border-zinc-800 rounded-2xl p-5 shadow-xl backdrop-blur-sm">
                    <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2 border-b border-zinc-800/80 pb-3 mb-4">
                      <User className="w-4 h-4 text-teal-400" />
                      Caller Info (Collected Live)
                    </h3>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-zinc-950/40 p-3 rounded-xl border border-zinc-900">
                        <span className="text-[10px] font-semibold text-zinc-500 uppercase block tracking-wider">Caller Name</span>
                        <input
                          type="text"
                          placeholder="Not collected"
                          className="bg-transparent border-0 border-b border-zinc-800 text-sm font-bold text-zinc-200 mt-0.5 block w-full focus:outline-none focus:border-teal-500 py-1"
                          value={editableName}
                          onChange={(e) => setEditableName(e.target.value)}
                          disabled={sessionState.is_booked}
                        />
                      </div>
                      <div className="bg-zinc-950/40 p-3 rounded-xl border border-zinc-900">
                        <span className="text-[10px] font-semibold text-zinc-500 uppercase block tracking-wider">Contact Number</span>
                        <input
                          type="text"
                          placeholder="Not collected"
                          className="bg-transparent border-0 border-b border-zinc-800 text-sm font-bold text-zinc-200 mt-0.5 block w-full focus:outline-none focus:border-teal-500 py-1"
                          value={editablePhone}
                          onChange={(e) => setEditablePhone(e.target.value)}
                          disabled={sessionState.is_booked}
                        />
                      </div>
                      <div className="bg-zinc-950/40 p-3 rounded-xl border border-zinc-900 col-span-2">
                        <span className="text-[10px] font-semibold text-zinc-500 uppercase block tracking-wider">Reason for Visit</span>
                        <input
                          type="text"
                          placeholder="Not collected"
                          className="bg-transparent border-0 border-b border-zinc-800 text-sm font-bold text-zinc-200 mt-0.5 block w-full focus:outline-none focus:border-teal-500 py-1"
                          value={editableReason}
                          onChange={(e) => setEditableReason(e.target.value)}
                          disabled={sessionState.is_booked}
                        />
                      </div>
                      <div className="bg-zinc-950/40 p-3 rounded-xl border border-zinc-900">
                        <span className="text-[10px] font-semibold text-zinc-500 uppercase block tracking-wider">Preferred Date/Time</span>
                        <input
                          type="text"
                          placeholder="Not collected"
                          className="bg-transparent border-0 border-b border-zinc-800 text-sm font-bold text-zinc-200 mt-0.5 block w-full focus:outline-none focus:border-teal-500 py-1"
                          value={editableTime}
                          onChange={(e) => setEditableTime(e.target.value)}
                          disabled={sessionState.is_booked}
                        />
                      </div>
                      <div className="bg-zinc-950/40 p-3 rounded-xl border border-zinc-900 flex flex-col justify-center">
                        <span className="text-[10px] font-semibold text-zinc-500 uppercase block tracking-wider">Booking Status</span>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          {sessionState.is_booked ? (
                            <span className="text-emerald-400 font-bold text-xs flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Booked
                            </span>
                          ) : (
                            <span className="text-zinc-500 font-bold text-xs">Not Booked</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {!sessionState.is_booked && (
                      <button
                        onClick={handleManualBook}
                        className="mt-4 w-full bg-teal-500 hover:bg-teal-600 text-black font-bold py-2.5 px-4 rounded-xl text-xs transition-all flex items-center justify-center gap-1.5 shadow-lg shadow-teal-500/10"
                      >
                        <CheckSquare className="w-4 h-4" />
                        Confirm & Save Booking to MySQL
                      </button>
                    )}
                  </div>

                  {/* Card 2: Real-time State & Status Indicators */}
                  <div className="bg-zinc-900/30 border border-zinc-800 rounded-2xl p-5 shadow-xl backdrop-blur-sm">
                    <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2 border-b border-zinc-800/80 pb-3 mb-4">
                      <Radio className="w-4 h-4 text-teal-400" />
                      Agent Real-Time State
                    </h3>

                    <div className="space-y-4">
                      {/* State Pulsator */}
                      <div className="flex items-center justify-between bg-zinc-950/60 border border-zinc-800 px-4 py-3 rounded-xl">
                        <span className="text-xs font-semibold text-zinc-400">Agent A State</span>
                        <div className="flex items-center gap-2">
                          <span className={`w-3 h-3 rounded-full ${
                            sessionState.agent_state === "speaking" ? "bg-blue-400 animate-ping" :
                            sessionState.agent_state === "thinking" ? "bg-amber-400 animate-ping" :
                            sessionState.agent_state === "monitoring" ? "bg-rose-500 animate-ping" :
                            "bg-emerald-400 animate-ping"
                          }`}></span>
                          <span className={`text-sm font-bold capitalize ${
                            sessionState.agent_state === "speaking" ? "text-blue-400" :
                            sessionState.agent_state === "thinking" ? "text-amber-400" :
                            sessionState.agent_state === "monitoring" ? "text-rose-400" :
                            "text-emerald-400"
                          }`}>
                            {sessionState.agent_state === "monitoring" ? "Supervisor Monitoring Mode" : sessionState.agent_state}
                          </span>
                        </div>
                      </div>

                      {/* Detail Metrics */}
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="bg-zinc-950/40 p-3 rounded-xl border border-zinc-900 flex justify-between items-center">
                          <span className="text-zinc-500 font-semibold">Call Status</span>
                          <span className="font-bold text-zinc-300 capitalize">{sessionState.call_status}</span>
                        </div>
                        <div className="bg-zinc-950/40 p-3 rounded-xl border border-zinc-900 flex justify-between items-center">
                          <span className="text-zinc-500 font-semibold">Transfer Status</span>
                          <span className={`font-bold capitalize ${
                            sessionState.transfer_status === "accepted" ? "text-emerald-400" :
                            sessionState.transfer_status === "calling" ? "text-amber-400 animate-pulse" :
                            sessionState.transfer_status === "declined" ? "text-rose-400" :
                            "text-zinc-500"
                          }`}>
                            {sessionState.transfer_status}
                          </span>
                        </div>
                        <div className="bg-zinc-950/40 p-3 rounded-xl border border-zinc-900 col-span-2 flex justify-between items-center">
                          <span className="text-zinc-500 font-semibold">Detected Intent</span>
                          <span className="font-bold text-teal-400">{sessionState.detected_intent}</span>
                        </div>
                        <div className="bg-zinc-950/40 p-3 rounded-xl border border-zinc-900 col-span-2 flex justify-between items-center">
                          <span className="text-zinc-500 font-semibold">Current Action</span>
                          <span className="font-bold text-zinc-300 truncate max-w-[200px]" title={sessionState.current_action}>
                            {sessionState.current_action}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Card 3: Watcher Controls & Takeover */}
                  <div className="bg-zinc-900/30 border border-zinc-800 rounded-2xl p-5 shadow-xl backdrop-blur-sm">
                    <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2 border-b border-zinc-800/80 pb-3 mb-4">
                      <ShieldAlert className="w-4 h-4 text-teal-400" />
                      Takeover & Warm Transfer Control
                    </h3>

                    <div className="space-y-4">
                      {/* Takeover Control */}
                      <div className="bg-zinc-950/40 border border-zinc-900 p-4 rounded-xl flex flex-col gap-3">
                        <div className="flex justify-between items-center">
                          <div>
                            <span className="text-sm font-bold block">Intervene Conversation</span>
                            <span className="text-[10px] text-zinc-400 block mt-0.5">Watcher takes over directly as representative</span>
                          </div>
                          {sessionState.takeover_active ? (
                            <span className="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded text-[10px] font-bold">
                              ACTIVE
                            </span>
                          ) : (
                            <span className="bg-zinc-800 text-zinc-500 px-2 py-0.5 rounded text-[10px] font-bold">
                              STANDBY
                            </span>
                          )}
                        </div>

                        {!sessionState.takeover_active ? (
                          <button
                            onClick={handleTakeover}
                            className="w-full bg-rose-500 hover:bg-rose-600 text-white font-bold py-2 px-4 rounded-lg text-xs transition-all flex items-center justify-center gap-2 shadow-lg shadow-rose-500/10"
                          >
                            <ShieldAlert className="w-3.5 h-3.5" />
                            Take Over Call (Mute Agent A)
                          </button>
                        ) : (
                          <button
                            onClick={toggleLocalMic}
                            className={`w-full py-2 px-4 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 border ${
                              isLocalMicMuted 
                                ? "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border-emerald-500/30" 
                                : "bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border-rose-500/30"
                            }`}
                          >
                            <Phone className="w-3.5 h-3.5" />
                            {isLocalMicMuted ? "Unmute My Mic to Speak" : "Mute My Mic (I am speaking)"}
                          </button>
                        )}
                      </div>

                      {/* Warm Transfer Simulators */}
                      {sessionState.transfer_status === "calling" && (
                        <div className="bg-zinc-950/40 border border-zinc-900 p-4 rounded-xl flex flex-col gap-3">
                          <div className="flex items-center gap-1.5 text-xs text-amber-400 font-bold">
                            <AlertCircle className="w-4 h-4" /> Twilio Calling Phone Outbound...
                          </div>
                          <p className="text-[10px] text-zinc-400 leading-normal">
                            Twilio is calling the representative. You can test outcomes by pressing either:
                          </p>
                          <div className="grid grid-cols-2 gap-3 pt-1">
                            <button
                              onClick={() => handleSimulateTransfer("accept")}
                              className="bg-emerald-500 hover:bg-emerald-600 text-black font-bold py-1.5 px-3 rounded-lg text-xs transition-all"
                            >
                              Accept (Bridge Call)
                            </button>
                            <button
                              onClick={() => handleSimulateTransfer("decline")}
                              className="bg-rose-500 hover:bg-rose-600 text-white font-bold py-1.5 px-3 rounded-lg text-xs transition-all border border-rose-700"
                            >
                              Decline (Refuse)
                            </button>
                          </div>
                        </div>
                      )}

                      <button
                        onClick={handleDisconnect}
                        className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold py-2.5 px-4 rounded-xl text-xs transition-all border border-zinc-700"
                      >
                        Disconnect Watcher
                      </button>
                    </div>
                  </div>

                  {/* Card 4: Live Conversation Simulator */}
                  <div className="bg-zinc-900/30 border border-zinc-800 rounded-2xl p-5 shadow-xl backdrop-blur-sm mt-6 animate-fade-in">
                    <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2 border-b border-zinc-800/80 pb-3 mb-4">
                      <Sparkles className="w-4 h-4 text-teal-400" />
                      Live Conversation Simulator
                    </h3>
                    
                    <div className="space-y-4">
                      <p className="text-[10px] text-zinc-400 leading-normal">
                        Mute or offline? Use this panel to type or click preset scripts. OpenAI will extract patient entities and auto-fill the form cards in real-time!
                      </p>
                      
                      {/* Presets */}
                      <div className="space-y-1.5">
                        <span className="text-[10px] font-bold text-zinc-500 block uppercase">Demo Preset Scripts</span>
                        <div className="flex flex-col gap-2">
                          <button
                            onClick={() => handleSimulateSpeech("Hi, my name is Sarah Jenkins, and I am calling because I have a really bad toothache in my back lower left jaw.")}
                            className="bg-zinc-950 hover:bg-zinc-900 border border-zinc-800/80 text-left px-3 py-2 rounded-lg text-xs leading-normal transition-all text-zinc-300 hover:text-white"
                          >
                            Pill 1: "Hi, I'm Sarah Jenkins... toothache."
                          </button>
                          <button
                            onClick={() => handleSimulateSpeech("My phone is 555-1234, and I would love to book an appointment next Monday at 10:00 AM if you have it open.")}
                            className="bg-zinc-950 hover:bg-zinc-900 border border-zinc-800/80 text-left px-3 py-2 rounded-lg text-xs leading-normal transition-all text-zinc-300 hover:text-white"
                          >
                            Pill 2: "My phone is 555-1234... Monday at 10 AM."
                          </button>
                          <button
                            onClick={() => handleSimulateSpeech("Can you transfer me to a human agent please? I have a question about wisdom teeth financing plans.")}
                            className="bg-zinc-950 hover:bg-zinc-900 border border-zinc-800/80 text-left px-3 py-2 rounded-lg text-xs leading-normal transition-all text-zinc-300 hover:text-white"
                          >
                            Pill 3: "Can you transfer me... financing plans."
                          </button>
                        </div>
                      </div>

                      {/* Custom Input */}
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="Type simulated patient speech..."
                          className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-teal-500 transition-colors text-zinc-100"
                          value={simulatedText}
                          onChange={(e) => setSimulatedText(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleSimulateSpeech(simulatedText)}
                        />
                        <button
                          onClick={() => handleSimulateSpeech(simulatedText)}
                          disabled={isSimulating}
                          className="bg-teal-500 hover:bg-teal-600 text-black font-bold px-4 py-2 rounded-xl text-xs transition-all disabled:opacity-50 flex items-center gap-1 shadow-lg shadow-teal-500/10"
                        >
                          Send
                        </button>
                      </div>
                    </div>
                  </div>

                </div>

                {/* Right Column (Live Transcript & Post Call Summary) - 7 Cols */}
                <div className="lg:col-span-7 flex flex-col gap-6">
                  
                  {/* Timeline Progression Progress */}
                  <div className="bg-zinc-900/30 border border-zinc-800 rounded-2xl p-5 shadow-xl backdrop-blur-sm">
                    <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2 border-b border-zinc-800/80 pb-3 mb-4">
                      <Clock className="w-4 h-4 text-teal-400" />
                      Live Call Event Timeline
                    </h3>
                    <div className="relative border-l border-zinc-800 ml-3 pl-6 space-y-4">
                      {/* Connection event */}
                      <div className="relative">
                        <span className="absolute -left-[30px] top-0 bg-teal-500 p-1 rounded-full text-black">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        </span>
                        <h4 className="text-xs font-bold text-zinc-200">Call Connected</h4>
                        <p className="text-[10px] text-zinc-400">Caller initiated WebRTC room connection</p>
                      </div>

                      {/* Name Collected event */}
                      {sessionState.caller_name && (
                        <div className="relative">
                          <span className="absolute -left-[30px] top-0 bg-teal-500 p-1 rounded-full text-black">
                            <User className="w-3.5 h-3.5" />
                          </span>
                          <h4 className="text-xs font-bold text-zinc-200">Identity Verified</h4>
                          <p className="text-[10px] text-zinc-400">Caller Name: {sessionState.caller_name}</p>
                        </div>
                      )}

                      {/* Booking Confirmed event */}
                      {sessionState.is_booked && (
                        <div className="relative">
                          <span className="absolute -left-[30px] top-0 bg-emerald-500 p-1 rounded-full text-black">
                            <Calendar className="w-3.5 h-3.5" />
                          </span>
                          <h4 className="text-xs font-bold text-emerald-400">Appointment Registered</h4>
                          <p className="text-[10px] text-zinc-400">Scheduled for {sessionState.preferred_date_time}</p>
                        </div>
                      )}

                      {/* Handoff Triggered event */}
                      {sessionState.call_status === "transferring" && (
                        <div className="relative">
                          <span className="absolute -left-[30px] top-0 bg-amber-500 p-1 rounded-full text-black">
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          </span>
                          <h4 className="text-xs font-bold text-amber-400">Outbound Handoff Initiated</h4>
                          <p className="text-[10px] text-zinc-400">Dialing human agent at Twilio handset...</p>
                        </div>
                      )}

                      {/* Takeover event */}
                      {sessionState.takeover_active && (
                        <div className="relative">
                          <span className="absolute -left-[30px] top-0 bg-rose-500 p-1 rounded-full text-black animate-pulse">
                            <ShieldAlert className="w-3.5 h-3.5" />
                          </span>
                          <h4 className="text-xs font-bold text-rose-400">Supervisor Takeover</h4>
                          <p className="text-[10px] text-zinc-400">Manual takeover completed. Supervisor speaking live.</p>
                        </div>
                      )}

                      {/* Ended event */}
                      {sessionState.call_status === "ended" && (
                        <div className="relative">
                          <span className="absolute -left-[30px] top-0 bg-zinc-700 p-1 rounded-full text-zinc-300">
                            <PhoneOff className="w-3.5 h-3.5" />
                          </span>
                          <h4 className="text-xs font-bold text-zinc-400">Call Concluded</h4>
                          <p className="text-[10px] text-zinc-400">Caller disconnected, post-call clinical summary compiled.</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Card 4: Live Transcript */}
                  <div className="bg-zinc-900/30 border border-zinc-800 rounded-2xl shadow-xl backdrop-blur-sm flex flex-col h-[350px]">
                    <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2 border-b border-zinc-800/80 p-5 pb-3">
                      <MessageSquare className="w-4 h-4 text-teal-400" />
                      Live Room Transcript (Sub-Millisecond Broadcaster)
                    </h3>

                    {/* Chat Area */}
                    <div className="flex-1 overflow-y-auto p-5 space-y-4">
                      {sessionState.transcript.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-zinc-500 text-xs italic">
                          Waiting for conversation to begin...
                        </div>
                      ) : (
                        sessionState.transcript.map((item, index) => {
                          const isAgent = item.speaker === "agent";
                          const isWatcher = item.speaker === "watcher";
                          return (
                            <div 
                              key={index}
                              className={`flex flex-col max-w-[85%] ${
                                isAgent ? "mr-auto items-start" : "ml-auto items-end"
                              }`}
                            >
                              <span className={`text-[9px] font-bold uppercase tracking-wider mb-1 ${
                                isAgent ? "text-teal-400" : isWatcher ? "text-rose-400" : "text-purple-400"
                              }`}>
                                {isAgent ? "🤖 Agent A" : isWatcher ? "👮 Watcher" : "👤 Caller"}
                              </span>
                              <div className={`p-3 rounded-2xl text-xs leading-relaxed ${
                                isAgent 
                                  ? "bg-teal-500/10 border border-teal-500/20 text-teal-100 rounded-tl-none" 
                                  : isWatcher 
                                  ? "bg-rose-500/10 border border-rose-500/20 text-rose-100 rounded-tr-none" 
                                  : "bg-purple-500/10 border border-purple-500/20 text-purple-100 rounded-tr-none"
                              }`}>
                                {item.text}
                              </div>
                            </div>
                          );
                        })
                      )}
                      <div ref={transcriptEndRef}></div>
                    </div>
                  </div>

                  {/* Card 5: Post Call Summary */}
                  {sessionState.call_status === "ended" && sessionState.post_call_summary && (
                    <div className="bg-zinc-900/30 border border-zinc-800 rounded-2xl p-5 shadow-xl backdrop-blur-sm animate-fade-in">
                      <h3 className="text-sm font-semibold text-teal-400 uppercase tracking-wider flex items-center gap-2 border-b border-zinc-800/80 pb-3 mb-4">
                        <FileText className="w-4 h-4 text-teal-400" />
                        🤖 OpenAI Post-Call Summary (Generated Live)
                      </h3>

                      <div className="prose prose-invert max-w-none text-xs leading-relaxed text-zinc-300 whitespace-pre-wrap font-sans bg-zinc-950/60 p-4 rounded-xl border border-zinc-900">
                        {sessionState.post_call_summary}
                      </div>
                    </div>
                  )}

                </div>

              </div>
            )}

          </div>
        )}

      </main>

      <footer className="mt-auto py-6 text-center text-xs text-zinc-500 border-t border-zinc-900">
        &copy; {new Date().getFullYear()} OpenVoice Portal. Powered by LiveKit, OpenAI, Deepgram, and Twilio.
      </footer>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView,
  StyleSheet, StatusBar, SafeAreaView, TextInput
} from 'react-native';
import * as Speech from 'expo-speech';
import AsyncStorage from '@react-native-async-storage/async-storage';

const Nova_API_URL = process.env.EXPO_PUBLIC_Nova_API_URL || 'http://192.168.1.100:8787/api/command';

export default function App() {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState([]);
  const [isThinking, setIsThinking] = useState(false);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const saved = await AsyncStorage.getItem('Nova_history');
      if (saved) setHistory(JSON.parse(saved));
    } catch {}
  };

  const saveHistory = async (newHistory) => {
    try {
      await AsyncStorage.setItem('Nova_history', JSON.stringify(newHistory.slice(-30)));
    } catch {}
  };

  const sendCommand = async () => {
    const userText = input.trim();
    if (!userText) return;

    setIsThinking(true);
    setInput('');

    try {
      const res = await fetch(Nova_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: userText }),
      });
      const data = await res.json();
      const reply = data.spoken_reply || 'Sorry, kuch samajh nahi aaya.';

      const newHistory = [
        ...history,
        { role: 'You', text: userText, time: new Date().toLocaleTimeString() },
        { role: 'Nova', text: reply, time: new Date().toLocaleTimeString() },
      ];
      setHistory(newHistory);
      saveHistory(newHistory);

      Speech.speak(reply, { language: 'hi-IN', rate: 0.95 });
    } catch (e) {
      const newHistory = [
        ...history,
        { role: 'You', text: userText, time: new Date().toLocaleTimeString() },
        { role: 'Nova', text: 'Backend unavailable. Check PC API URL.', time: new Date().toLocaleTimeString() },
      ];
      setHistory(newHistory);
      saveHistory(newHistory);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <SafeAreaView style={s.safe}>
      <StatusBar barStyle="light-content" backgroundColor="#0f0f1a" />

      <View style={s.header}>
        <Text style={s.logo}>N O V A</Text>
        <Text style={s.tagline}>100% Free Mobile Client</Text>
      </View>

      <ScrollView style={s.history} contentContainerStyle={{ paddingBottom: 16 }}>
        {history.length === 0 && (
          <Text style={s.empty}>
            Type command and send. Example: {'\n'}- reminder set karo 10 minute mein
          </Text>
        )}
        {history.map((item, i) => (
          <View key={i} style={[s.bubble, item.role === 'You' ? s.userBubble : s.botBubble]}>
            <Text style={s.bubbleRole}>{item.role} · {item.time}</Text>
            <Text style={s.bubbleText}>{item.text}</Text>
          </View>
        ))}
      </ScrollView>

      <View style={s.inputBar}>
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Type command..."
          placeholderTextColor="#666"
          style={s.input}
        />
        <TouchableOpacity style={s.sendBtn} onPress={sendCommand}>
          <Text style={s.sendTxt}>{isThinking ? '...' : 'Send'}</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0f0f1a' },
  header: { alignItems: 'center', paddingVertical: 18, borderBottomWidth: 1, borderColor: '#1e1e35' },
  logo: { fontSize: 24, fontWeight: '700', color: '#7c6bf7', letterSpacing: 6 },
  tagline: { fontSize: 12, color: '#555577', marginTop: 4 },
  history: { flex: 1, paddingHorizontal: 16, paddingTop: 12 },
  empty: { color: '#444466', textAlign: 'center', marginTop: 30, lineHeight: 22 },
  bubble: { marginBottom: 10, padding: 12, borderRadius: 14, maxWidth: '85%' },
  userBubble: { backgroundColor: '#1c1c38', alignSelf: 'flex-end' },
  botBubble: { backgroundColor: '#16163a', alignSelf: 'flex-start', borderLeftWidth: 2, borderLeftColor: '#7c6bf7' },
  bubbleRole: { fontSize: 10, color: '#7c6bf7', marginBottom: 4, fontWeight: '600' },
  bubbleText: { color: '#cccce8', fontSize: 15, lineHeight: 22 },
  inputBar: { flexDirection: 'row', padding: 12, borderTopWidth: 1, borderColor: '#1e1e35' },
  input: { flex: 1, color: '#ddd', backgroundColor: '#17172c', borderRadius: 10, paddingHorizontal: 12, marginRight: 10 },
  sendBtn: { backgroundColor: '#7c6bf7', borderRadius: 10, paddingHorizontal: 16, justifyContent: 'center' },
  sendTxt: { color: '#fff', fontWeight: '700' },
});

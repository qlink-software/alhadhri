/** @odoo-module */

import { Component, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class SoundNotification extends Component {
    static template = "qlk_management.SoundNotificationTemplate";
    static props = { ...standardActionServiceProps };

    setup() {
        this.notification = useService("notification");
        this.action = this.props.action;

        onWillStart(async () => {
            await this._playSound();
        });

        // onMounted(() => {
        //     // Remove after 3 seconds
        //     setTimeout(() => {
        //         if (this.el) {
        //             this.el.remove();
        //         }
        //     }, 3000);
        
        //     // Close button
        //     const btn = this.el.querySelector(".o_notification_close");
        //     if (btn) {
        //         btn.addEventListener("click", () => {
        //             this.el.remove();
        //         });
        //     }
        // });
        
    }

    async _playSound() {
        const params = this.action.params || {};
        const message = params.message || "You have a new notification";
    
        // If a soundStream is provided, play it first
        let soundStream = params.sound_stream;
        if (soundStream) {
            this._decodeAndPlay(soundStream);
            return;
        }
    
        // Otherwise, read the message aloud using Web Speech API
        if ("speechSynthesis" in window) {
            const utterance = new SpeechSynthesisUtterance(message);
            utterance.lang = "en-US"; // adjust language if needed
            utterance.pitch = 1;       // default pitch
            utterance.rate = 1;        // normal speed
            window.speechSynthesis.speak(utterance);
        } else {
            // fallback beep if speech not supported
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioCtx.createOscillator();
            oscillator.type = "sine";
            oscillator.frequency.setValueAtTime(440, audioCtx.currentTime);
            oscillator.connect(audioCtx.destination);
            oscillator.start();
            oscillator.stop(audioCtx.currentTime + 0.3);
        }
    }
    
    _decodeAndPlay(data) {
        try {
            let audio;
            if (data.startsWith("http") || data.startsWith("/")) {
                audio = new Audio(data); // URL
            } else {
                // base64 decoding
                const byteCharacters = atob(data);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const audioBlob = new Blob([byteArray], { type: "audio/mp3" });
                const audioUrl = URL.createObjectURL(audioBlob);
                audio = new Audio(audioUrl);
            }
            audio.play().catch(err => console.warn("Could not play sound:", err));
        } catch (e) {
            console.error("Error decoding sound:", e);
        }
    }

    // _showNotification() {
    //     const params = this.action.params || {};
    //     if (params.title && params.message) {
    //         this.notification.add(params.message, {
    //             title: params.title,
    //             type: "info",
    //             sticky: params.sticky || false,
    //         });
    //     }
    // }
}

// register the action
registry.category("actions").add("play_sound_with_notification", SoundNotification);

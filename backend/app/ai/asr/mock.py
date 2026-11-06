"""Mock ASR provider — clearly flagged, deterministic demo transcripts.

Used only when ASR_PROVIDER=mock. Produces language-appropriate demo lecture
text spread over the *actual* VAD-derived chunk timings so the rest of the
pipeline (segment references, transcript UI, notes, quiz) behaves exactly as
it would with real recognition output.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import List

from app.ai.asr.base import ASRProvider
from app.ai.types import ASRResult, ASRSegmentResult, ProviderInfo
from app.core.languages import get_language

logger = logging.getLogger("lecturelens.asr.mock")

# A short demo lecture ("Introduction to Operating Systems") in each supported
# language. Clearly demo content — not a real recording.
DEMO_LINES = {
    "en": [
        "Welcome to this lecture on operating systems.",
        "An operating system manages hardware resources and provides services to applications.",
        "Process management is one of the core responsibilities of an operating system.",
        "A process is an instance of a program that is being executed.",
        "The scheduler decides which process runs next on the CPU.",
        "Memory management allocates RAM to processes and protects them from each other.",
        "Virtual memory lets a system run programs larger than physical RAM.",
        "File systems organize data on storage devices into files and directories.",
        "Deadlock occurs when processes wait for each other indefinitely.",
        "The four necessary conditions for deadlock are mutual exclusion, hold and wait, no preemption, and circular wait.",
        "Let us now look at a simple example of a round robin scheduler.",
        "In round robin, each process gets a fixed time slice in a cyclic order.",
        "To summarise, the operating system abstracts hardware and isolates processes.",
        "Please review the notes on deadlock avoidance before the next class.",
    ],
    "hi": [
        "संचालन प्रणाली के इस व्याख्यान में आपका स्वागत है।",
        "संचालन प्रणाली हार्डवेयर संसाधनों का प्रबंधन करती है और अनुप्रयोगों को सेवाएँ प्रदान करती है।",
        "प्रक्रिया प्रबंधन संचालन प्रणाली की मुख्य जिम्मेदारियों में से एक है।",
        "प्रक्रिया क्रियान्वित किए जा रहे कार्यक्रम का एक उदाहरण है।",
        "शेड्यूलर तय करता है कि CPU पर अगली प्रक्रिया कौन चलेगी।",
        "स्मृति प्रबंधन प्रक्रियाओं को RAM आवंटित करता है।",
        "वर्चुअल मेमोरी से भौतिक RAM से बड़े कार्यक्रम चलाए जा सकते हैं।",
        "फ़ाइल प्रणाली स्टोरेज पर डेटा को फ़ाइलों और निर्देशिकाओं में व्यवस्थित करती है।",
        "डेडलॉक तब होता है जब प्रक्रियाएँ एक दूसरे का इंतज़ार करती रहती हैं।",
        "डेडलॉक की चार आवश्यक शर्तें पारस्परिक अनन्यता, होल्ड एंड वेट, नो प्रीम्प्शन और सर्कुलर वेट हैं।",
        "अब हम राउंड रॉबिन शेड्यूलर का एक सरल उदाहरण देखेंगे।",
        "राउंड रॉबिन में प्रत्येक प्रक्रिया को चक्रीय क्रम में एक निश्चित समय मिलता है।",
        "संक्षेप में, संचालन प्रणाली हार्डवेयर को अमूर्त बनाती है और प्रक्रियाओं को अलग रखती है।",
        "अगली कक्षा से पहले डेडलॉक अवॉइडेंस के नोट्स दोहराएँ।",
    ],
    "kn": [
        "ಈ ಕಾರ್ಯಾಚರಣಾ ವ್ಯವಸ್ಥೆಯ ಉಪನ್ಯಾಸಕ್ಕೆ ಸ್ವಾಗತ.",
        "ಕಾರ್ಯಾಚರಣಾ ವ್ಯವಸ್ಥೆಯು ಯಂತ್ರಾಂಶ ಸಂಪನ್ಮೂಲಗಳನ್ನು ನಿರ್ವಹಿಸುತ್ತದೆ ಮತ್ತು ಅಪ್ಲಿಕೇಶನ್‌ಗಳಿಗೆ ಸೇವೆಗಳನ್ನು ಒದಗಿಸುತ್ತದೆ.",
        "ಪ್ರಕ್ರಿಯಾ ನಿರ್ವಹಣೆ ಕಾರ್ಯಾಚರಣಾ ವ್ಯವಸ್ಥೆಯ ಪ್ರಮುಖ ಜವಾಬ್ದಾರಿಗಳಲ್ಲಿ ಒಂದು.",
        "ಪ್ರಕ್ರಿಯೆಯು ಕಾರ್ಯಗತಗೊಳಿಸಲಾಗುತ್ತಿರುವ ಪ್ರೋಗ್ರಾಮ್‌ನ ಒಂದು ನಮೂನೆ.",
        "ಶೆಡ್ಯೂಲರ್ CPU ನಲ್ಲಿ ಮುಂದಿನ ಯಾವ ಪ್ರಕ್ರಿಯೆ ಚಲಿಸಬೇಕೆಂದು ನಿರ್ಧರಿಸುತ್ತದೆ.",
        "ಸ್ಮರಣಾ ನಿರ್ವಹಣೆಯು ಪ್ರಕ್ರಿಯೆಗಳಿಗೆ RAM ಅನ್ನು ನಿಯೋಜಿಸುತ್ತದೆ.",
        "ವರ್ಚುವಲ್ ಮೆಮೊರಿಯಿಂದ ದೈಹಿಕ RAM ಗಿಂತ ದೊಡ್ಡ ಪ್ರೋಗ್ರಾಮ್‌ಗಳನ್ನು ಚಲಾಯಿಸಬಹುದು.",
        "ಫೈಲ್ ವ್ಯವಸ್ಥೆಯು ಸಂಗ್ರಹಣೆಯಲ್ಲಿ ಡೇಟಾವನ್ನು ಫೈಲ್‌ಗಳು ಮತ್ತು ಕೋಶಗಳಲ್ಲಿ ಸಂಘಟಿಸುತ್ತದೆ.",
        "ಡೆಡ್‌ಲಾಕ್ ಎಂದರೆ ಪ್ರಕ್ರಿಯೆಗಳು ಪರಸ್ಪರ ನಿರಂತರವಾಗಿ ಕಾಯುವುದು.",
        "ಡೆಡ್‌ಲಾಕ್‌ಗೆ ಅಗತ್ಯವಾದ ನಾಲ್ಕು ಷರತ್ತುಗಳು ಪರಸ್ಪರ ಹೊಂದಾಣಿಕೆ, ಹೋಲ್ಡ್ ಅಂಡ್ ವೇಟ್, ನೋ ಪ್ರೀಂಪ್ಶನ್ ಮತ್ತು ಸರ್ಕ್ಯುಲರ್ ವೇಟ್.",
        "ಈಗ ರೌಂಡ್ ರಾಬಿನ್ ಶೆಡ್ಯೂಲರ್‌ನ ಸರಳ ಉದಾಹರಣೆಯನ್ನು ನೋಡೋಣ.",
        "ರೌಂಡ್ ರಾಬಿನ್‌ನಲ್ಲಿ ಪ್ರತಿ ಪ್ರಕ್ರಿಯೆಗೆ ಆವರ್ತನ ಕ್ರಮದಲ್ಲಿ ನಿಗದಿತ ಸಮಯ ಸಿಗುತ್ತದೆ.",
        "ಸಂಕ್ಷಿಪ್ತವಾಗಿ, ಕಾರ್ಯಾಚರಣಾ ವ್ಯವಸ್ಥೆಯು ಯಂತ್ರಾಂಶವನ್ನು ಅಮೂರ್ತಗೊಳಿಸುತ್ತದೆ.",
        "ಮುಂದಿನ ತರಗತಿಗೂ ಮೊದಲು ಡೆಡ್‌ಲಾಕ್ ತಪ್ಪಿಸುವಿಕೆಯ ಟಿಪ್ಪಣಿಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.",
    ],
    "ta": [
        "இந்த இயக்க முறைமை விரிவுரைக்கு வரவேற்கிறோம்.",
        "இயக்க முறைமை வன்பொருள் வளங்களை நிர்வகித்து பயன்பாடுகளுக்கு சேவைகளை வழங்குகிறது.",
        "செயல்முறை மேலாண்மை இயக்க முறைமையின் முக்கிய பொறுப்புகளில் ஒன்றாகும்.",
        "செயல்படுத்தப்படும் நிரலின் ஒரு நிகழ்வே செயல்முறை ஆகும்.",
        "அடுத்து எந்த செயல்முறை CPU இல் இயங்க வேண்டும் என்பதை திட்டமிடுபவர் முடிவு செய்கிறார்.",
        "நினைவக மேலாண்மை செயல்முறைகளுக்கு RAM ஒதுக்குகிறது.",
        "மெய்நிகர் நினைவகம் உடல் RAM ஐ விட பெரிய நிரல்களை இயக்க அனுமதிக்கிறது.",
        "கோப்பு முறைமை சேமிப்பில் தரவை கோப்புகள் மற்றும் கோப்புறைகளாக ஒழுங்குபடுத்துகிறது.",
        "செயல்முறைகள் ஒன்றையொன்று காத்திருக்கும் போது இறந்தநிலை ஏற்படுகிறது.",
        "இறந்தநிலைக்கான நான்கு தேவையான நிபந்தனைகள் பரஸ்பர பிரத்தியேகம், வைத்திருத்தல் மற்றும் காத்திருத்தல், முன்னுரிமை இல்லாமை, வட்டக் காத்திருத்தல் ஆகியவை.",
        "இப்போது வட்டமுறை திட்டமிடுபவரின் எளிய எடுத்துக்காட்டைப் பார்ப்போம்.",
        "வட்டமுறையில் ஒவ்வொரு செயல்முறைக்கும் சுழற்சி வரிசையில் நிலையான நேரம் கிடைக்கிறது.",
        "சுருக்கமாக, இயக்க முறைமை வன்பொருளை நுண்ணியதாக மாற்றி செயல்முறைகளை தனிமைப்படுத்துகிறது.",
        "அடுத்த வகுப்புக்கு முன் இறந்தநிலை தவிர்ப்பு குறிப்புகளை மறுஆய்வு செய்யுங்கள்.",
    ],
    "te": [
        "ఈ ఆపరేటింగ్ సిస్టమ్ లెక్చర్‌కు స్వాగతం.",
        "ఆపరేటింగ్ సిస్టమ్ హార్డ్‌వేర్ వనరులను నిర్వహించి అప్లికేషన్‌లకు సేవలను అందిస్తుంది.",
        "ప్రాసెస్ నిర్వహణ ఆపరేటింగ్ సిస్టమ్ యొక్క ప్రధాన బాధ్యతలలో ఒకటి.",
        "అమలు చేయబడుతున్న ప్రోగ్రామ్ యొక్క ఒక సంఘటనే ప్రాసెస్.",
        "CPU లో తదుపరి ఏ ప్రాసెస్ నడవాలో షెడ్యూలర్ నిర్ణయిస్తుంది.",
        "మెమరీ నిర్వహణ ప్రాసెస్‌లకు RAM కేటాయిస్తుంది.",
        "వర్చువల్ మెమరీ ఫిజికల్ RAM కంటే పెద్ద ప్రోగ్రామ్‌లను నడపడానికి అనుమతిస్తుంది.",
        "ఫైల్ సిస్టమ్ స్టోరేజ్‌లోని డేటాను ఫైల్‌లు మరియు డైరెక్టరీలుగా నిర్వహిస్తుంది.",
        "ప్రాసెస్‌లు ఒకదానికొకటి శాశ్వతంగా వేచి ఉన్నప్పుడు డెడ్‌లాక్ సంభవిస్తుంది.",
        "డెడ్‌లాక్‌కు అవసరమైన నాలుగు షరతులు పరస్పర నిషేధం, హోల్డ్ అండ్ వెయిట్, నో ప్రీంప్షన్ మరియు సర్క్యులర్ వెయిట్.",
        "ఇప్పుడు రౌండ్ రాబిన్ షెడ్యూలర్ యొక్క సరళమైన ఉదాహరణను చూద్దాం.",
        "రౌండ్ రాబిన్‌లో ప్రతి ప్రాసెస్‌కు చక్రీయ క్రమంలో స్థిరమైన టైమ్ స్లైస్ లభిస్తుంది.",
        "సంగ్రహంగా, ఆపరేటింగ్ సిస్టమ్ హార్డ్‌వేర్‌ను సూక్ష్మీకరించి ప్రాసెస్‌లను వేరు చేస్తుంది.",
        "తదుపరి తరగతికి ముందు డెడ్‌లాక్ నివారణ గమనికలను సమీక్షించండి.",
    ],
    "ml": [
        "ഈ ഓപ്പറേറ്റിംഗ് സിസ്റ്റം പ്രഭാഷണത്തിലേക്ക് സ്വാഗതം.",
        "ഓപ്പറേറ്റിംഗ് സിസ്റ്റം ഹാർഡ്‌വെയർ വിഭവങ്ങൾ കൈകാര്യം ചെയ്യുകയും പ്രയോഗങ്ങൾക്ക് സേവനങ്ങൾ നൽകുകയും ചെയ്യുന്നു.",
        "പ്രക്രിയാ ഭരണം ഓപ്പറേറ്റിംഗ് സിസ്റ്റത്തിന്റെ പ്രധാന ഉത്തരവാദിത്തങ്ങളിൽ ഒന്നാണ്.",
        "നടപ്പിലാക്കിക്കൊണ്ടിരിക്കുന്ന പ്രോഗ്രാമിന്റെ ഒരു ഇൻസ്റ്റൻസാണ് പ്രക്രിയ.",
        "അടുത്തതായി ഏത് പ്രക്രിയ CPU-യിൽ പ്രവർത്തിക്കണമെന്ന് ഷെഡ്യൂലർ തീരുമാനിക്കുന്നു.",
        "മെമ്മറി ഭരണം പ്രക്രിയകൾക്ക് RAM വിതരണം ചെയ്യുന്നു.",
        "വർച്ചുവൽ മെമ്മറി ഉപയോഗിച്ച് ഭൗതിക RAM-നേക്കാൾ വലിയ പ്രോഗ്രാമുകൾ പ്രവർത്തിപ്പിക്കാം.",
        "ഫയൽ സിസ്റ്റം സ്റ്റോറേജിലെ ഡാറ്റ ഫയലുകളിലും ഡയറക്ടറികളിലും ക്രമീകരിക്കുന്നു.",
        "പ്രക്രിയകൾ പരസ്പരം എല്ലാക്കാലവും കാത്തിരിക്കുമ്പോൾ ഡെഡ്‌ലോക്ക് സംഭവിക്കുന്നു.",
        "ഡെഡ്‌ലോക്കിന് ആവശ്യമായ നാല് വ്യവസ്ഥകൾ പരസ്പര എക്സ്ക്ലൂഷൻ, ഹോൾഡ് ആൻഡ് വെയിറ്റ്, നോ പ്രീമ്പ്ഷൻ, സർക്കുലർ വെയിറ്റ് എന്നിവയാണ്.",
        "ഇപ്പോൾ റൗണ്ട് റോബിൻ ഷെഡ്യൂലറിന്റെ ലളിതമായ ഉദാഹരണം നോക്കാം.",
        "റൗണ്ട് റോബിനിൽ ഓരോ പ്രക്രിയയ്ക്കും ആവർത്തന ക്രമത്തിൽ നിശ്ചിത സമയം ലഭിക്കുന്നു.",
        "ചുരുക്കത്തിൽ, ഓപ്പറേറ്റിംഗ് സിസ്റ്റം ഹാർഡ്‌വെയറിനെ അമൂർത്തമാക്കുകയും പ്രക്രിയകളെ വേർതിരിക്കുകയും ��െയ്യുന്നു.",
        "അടുത്ത ക്ലാസിന് മുമ്പ് ഡെഡ്‌ലോക്ക് ഒഴിവാക്കലിന്റെ കുറിപ്പുകൾ അവലോകനം ചെയ്യുക.",
    ],
}


class MockASR(ASRProvider):
    name = "asr"

    def info(self) -> ProviderInfo:
        from app.ai.types import ProviderInfo
        return ProviderInfo(
            name="asr", provider="mock", mode="mock", loaded=True,
            detail="Demo transcripts (no speech recognition performed).",
        )

    def transcribe(self, audio_path: Path, language: str,
                   chunk_times: List[tuple]) -> ASRResult:
        from app.ai.types import ASRSegmentResult
        lang = get_language(language).key
        lines = DEMO_LINES.get(lang, DEMO_LINES["en"])
        # Deterministic pseudo-random ordering seed from the audio file identity
        seed = int(hashlib.md5(f"{audio_path.name}:{lang}".encode()).hexdigest()[:8], 16)
        ordered = lines[seed % len(lines):] + lines[:seed % len(lines)]

        results: List[ASRSegmentResult] = []
        line_i = 0
        n_chunks = max(1, len(chunk_times))
        for i, (start, end) in enumerate(chunk_times, start=1):
            # Distribute demo lines across chunks proportional to duration
            take = max(1, round(len(ordered) * ((end - start) / max(
                0.001, chunk_times[-1][1] - chunk_times[0][0]))))
            part = []
            for _ in range(take):
                part.append(ordered[line_i % len(ordered)])
                line_i += 1
            text = " ".join(part)
            results.append(ASRSegmentResult(
                start=start, end=end, text=text, language=language))

        logger.info("Mock ASR produced %d segments (language=%s)", len(results), language)
        return ASRResult(
            segments=results, language=language, is_mock=True, provider="mock",
            detail="Demo transcript generated by MockASR.",
        )

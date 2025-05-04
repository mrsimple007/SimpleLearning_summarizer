GEMINI_MODEL = "gemini-2.0-flash"

DEFAULT_TEMPERATURE = 0.7

# First starts asking for the language from user ru/en/uz with flags, and saves to database
# /settings command to view current settings - language, quiz type (open ended/multiple choice) with buttons. 5 default questions for each quiz type. And also, settings of the default option for summarize or generate quiz.
# /start command to welcome user, if user is not in the database, it should ask for the language. If yes, then just welcome user. and ask what document the user wants to summarize
# /help command to view the help menu
# if the user wants to change the language, it changes the language and saves it to the database
# Bot can process video, audio, image, pdf, docx, txt, url, and text. After getting the file, it should ask for the language again,and it will be added to the prompt to generate answers
# If the user wants to summarize, it will summarize the text and send it to the user with beautiful formatting.
# add typing function to the bot
# bot should respond to the user's message in the same language as the language that the user chose.
# i have already supabase database, and i have already created the table for the user data.
#             supabase.table('tg_bot_users').upsert({
            #     'user_id': user.id,
            #     'first_name': user.first_name,
            #     'last_name': user.last_name if user.last_name else None,
            #     'username': user.username if user.username else None,
            #     'last_activity': datetime.now().isoformat()
            # }, on_conflict='user_id').execute()

                # [
                #     InlineKeyboardButton(get_translation(language, 'language'), callback_data="settings_lang"),
                # ]



# def main() -> None:
#     """Start the bot."""
#     application = Application.builder().token(BOT_TOKEN).build()

#     # Add conversation handler
#     conv_handler = ConversationHandler(
#         entry_points=[CommandHandler("start", start)],
#         states={
#             LANGUAGE: [CallbackQueryHandler(language_selection)],
#             CONTENT: [MessageHandler(filters.TEXT | filters.Document.PDF, handle_content)],
#             PROCESSING: [CallbackQueryHandler(process_content)],
#         },
#         fallbacks=[CommandHandler("start", start)],
#     )

#     application.add_handler(conv_handler)
#     application.add_handler(CommandHandler("settings", settings_command))
#     application.add_handler(CommandHandler("help", help_command))

#     # Run the bot
#     application.run_polling()

# if __name__ == "__main__":
#     main() 


# from prompts import ANALYSIS_PROMPT_TEMPLATE_GEMINI, SYSTEM_PROMPT
# os.environ["GOOGLE_API_KEY"] = active_key


# language_instruction = f"\nIMPORTANT: Generate ALL content in {language} language."
# prompt = base_prompt + language_instruction

    
# try:
#         messages = [
#             {"role": "system", "content": SYSTEM_PROMPT},
#             {"role": "user", "content": prompt}
#         ]
        
#         response = llm.invoke(messages)
    
# from langchain_google_genai import ChatGoogleGenerativeAI

# # Set environment variable for API key
# active_key = "AIzaSyDemsCp7JIdRNDRyP6DkYdMox1DLZwPcPE"
# os.environ["GOOGLE_API_KEY"] = active_key

# # Initialize LLM
# llm = ChatGoogleGenerativeAI(
#     model=GEMINI_MODEL,
#     temperature=DEFAULT_TEMPERATURE,
#     max_retries=3
# )




# Ver 1.1
GEMINI_MODEL = "gemini-2.0-flash"

DEFAULT_TEMPERATURE = 0.7

# First starts asking for the language from user ru/en/uz with flags, and saves to database
# /settings command to view current settings - language, quiz type (open ended/multiple choice) with buttons. 5 default questions for each quiz type.
# /start command to start the quiz
# /help command to view the help menu
# /share command to share the quiz. Quiz can be shared as a message or a file. And if it is a multiple choice quiz it should be pool questions with telegram api bot.
# after the quiz is finished, it shows the results and asks if the user wants to save the quiz
# if the user wants to share the quiz, it sends the quiz to the user's telegram
# if the user wants to change the language, it changes the language and saves it to the database
# if the user wants to change the quiz type, it changes the quiz type and saves it to the database
# Bot can process pdf, docx, txt, and text. After getting the file, it should ask for the language again,and it will be added to the prompt to generate answers. And then, it will ask for summarize or generate quiz.
# If the user wants to summarize, it will summarize the text and send it to the user with beautiful formatting.
# If the user wants to generate quiz, it will generate quiz based on the text and send it to the user with beautiful formatting.
# add typing function to the bot when gemini is generating the quiz or summary
# bot should respond to the user's message in the same language as the language that the user chose.
# i have already supabase database, and i have already created the table for the user data.
#             supabase.table('tg_bot_users').upsert({
            #     'user_id': user.id,
            #     'first_name': user.first_name,
            #     'last_name': user.last_name if user.last_name else None,
            #     'username': user.username if user.username else None,
            #     'last_activity': datetime.now().isoformat()
            # }, on_conflict='user_id').execute()

                # [
                #     InlineKeyboardButton(get_translation(language, 'language'), callback_data="settings_lang"),
                #     InlineKeyboardButton(get_translation(language, 'quiz_type'), callback_data="settings_quiz"),
                # ]



# def main() -> None:
#     """Start the bot."""
#     application = Application.builder().token(BOT_TOKEN).build()

#     # Add conversation handler
#     conv_handler = ConversationHandler(
#         entry_points=[CommandHandler("start", start)],
#         states={
#             LANGUAGE: [CallbackQueryHandler(language_selection)],
#             QUIZ_TYPE: [CallbackQueryHandler(quiz_type_selection)],
#             CONTENT: [MessageHandler(filters.TEXT | filters.Document.PDF, handle_content)],
#             PROCESSING: [CallbackQueryHandler(process_content)],
#         },
#         fallbacks=[CommandHandler("start", start)],
#     )

#     application.add_handler(conv_handler)
#     application.add_handler(CommandHandler("settings", settings_command))
#     application.add_handler(CommandHandler("help", help_command))
#     application.add_handler(CallbackQueryHandler(settings_callback, pattern="^(settings_|lang_|quiz_)"))

#     # Run the bot
#     application.run_polling()

# if __name__ == "__main__":
#     main() 


# language_instruction = f"\nIMPORTANT: Generate ALL content (including topic names, key concepts, summaries, and quiz questions) in {language} language."
# prompt = base_prompt + language_instruction

    
# try:
#         messages = [
#             {"role": "system", "content": SYSTEM_PROMPT},
#             {"role": "user", "content": prompt}
#         ]
        
#         response = llm.invoke(messages)
    






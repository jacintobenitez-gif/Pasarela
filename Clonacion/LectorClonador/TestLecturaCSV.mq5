//+------------------------------------------------------------------+
//|                                            TestLecturaCSV.mq5    |
//|   Script de prueba para leer archivo CSV desde Common Files     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025"
#property link      "https://www.mql5.com"
#property version   "1.00"
#property script_show_inputs

input string InpTestFileName = "TradeEvents_test.csv"; // Nombre del archivo de prueba

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{
   Print("========================================");
   Print("TEST: Lectura de archivo CSV");
   Print("========================================");
   Print("Archivo a leer: ", InpTestFileName);
   Print("Ubicación: Common\\Files");
   Print("");
   
   // Abrir archivo en modo BINARIO para evitar problemas de codificación
   int handle = FileOpen(InpTestFileName,
                         FILE_READ | FILE_BIN | FILE_COMMON |
                         FILE_SHARE_READ | FILE_SHARE_WRITE);
   
   if(handle == INVALID_HANDLE)
   {
      int err = GetLastError();
      Print("ERROR: No se pudo abrir el archivo. Error=", err);
      if(err == 4103)
         Print("El archivo no existe. Verifica que esté en Common\\Files");
      return;
   }
   
   Print("✓ Archivo abierto correctamente en modo BINARIO. Handle=", handle);
   
   // Verificar tamaño
   ulong file_size = FileSize(handle);
   Print("Tamaño del archivo: ", file_size, " bytes");
   Print("");
   
   if(file_size == 0)
   {
      Print("ERROR: Archivo vacío");
      FileClose(handle);
      return;
   }
   
   // ============================================
   // LEER ARCHIVO COMPLETO EN MODO BINARIO
   // ============================================
   Print("--- Leyendo archivo completo en modo binario ---");
   
   uchar bytes[];
   ArrayResize(bytes, (int)file_size);
   uint bytes_read = FileReadArray(handle, bytes, 0, (int)file_size);
   
   FileClose(handle);
   
   Print("Bytes leídos: ", bytes_read, " de ", file_size);
   Print("");
   
   if(bytes_read == 0)
   {
      Print("ERROR: No se pudieron leer bytes del archivo");
      return;
   }
   
   // Mostrar primeros bytes en hexadecimal
   Print("Primeros 50 bytes (hex):");
   string hex_str = "";
   for(int i = 0; i < 50 && i < bytes_read; i++)
   {
      hex_str += StringFormat("%02X ", bytes[i]);
      if((i + 1) % 16 == 0)
         hex_str += "\n";
   }
   Print(hex_str);
   Print("");
   
   // ============================================
   // CONVERTIR BYTES A STRING
   // ============================================
   Print("--- Convirtiendo bytes a string ---");
   
   // Detectar BOM UTF-8 (EF BB BF)
   int start_pos = 0;
   int content_size = bytes_read;
   if(bytes_read >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF)
   {
      Print("BOM UTF-8 detectado (EF BB BF), saltándolo");
      start_pos = 3;
      content_size = bytes_read - 3;
   }
   else
   {
      Print("No se detectó BOM UTF-8");
   }
   
   // Crear array de bytes sin BOM si es necesario
   uchar content_bytes[];
   if(start_pos > 0)
   {
      ArrayResize(content_bytes, content_size);
      ArrayCopy(content_bytes, bytes, 0, start_pos, content_size);
   }
   else
   {
      content_bytes = bytes;
   }
   
   // Convertir a string usando UTF-8 (65001)
   Print("Convirtiendo usando UTF-8 (65001)...");
   string file_content = CharArrayToString(content_bytes, 0, WHOLE_ARRAY, 65001);
   
   Print("Longitud del string (UTF-8): ", StringLen(file_content), " caracteres");
   
   // Si está vacío o tiene caracteres extraños, intentar ANSI
   if(StringLen(file_content) == 0)
   {
      Print("String vacío con UTF-8, intentando ANSI...");
      file_content = CharArrayToString(content_bytes, 0, WHOLE_ARRAY, 0);
      Print("Longitud del string (ANSI): ", StringLen(file_content), " caracteres");
   }
   
   if(StringLen(file_content) == 0)
   {
      Print("ERROR: No se pudo convertir el contenido a string");
      return;
   }
   
   // Mostrar primeras líneas del contenido
   Print("");
   Print("Primeras 500 caracteres del contenido:");
   string preview = StringSubstr(file_content, 0, 500);
   Print(preview);
   Print("...");
   Print("");
   
   // ============================================
   // PARSEAR LÍNEAS
   // ============================================
   Print("--- Parseando líneas ---");
   
   // Dividir por líneas
   string lines[];
   int line_count = 0;
   
   // Intentar con \r primero (Windows)
   string temp_lines[];
   int temp_count = StringSplit(file_content, '\r', temp_lines);
   
   if(temp_count > 1)
   {
      ArrayResize(lines, temp_count);
      for(int i = 0; i < temp_count; i++)
      {
         string clean = temp_lines[i];
         StringReplace(clean, "\n", "");
         lines[i] = clean;
      }
      line_count = temp_count;
      Print("Líneas encontradas (separador \\r): ", line_count);
   }
   else
   {
      // Usar \n (Unix)
      line_count = StringSplit(file_content, '\n', lines);
      Print("Líneas encontradas (separador \\n): ", line_count);
   }
   
   Print("");
   
   // Mostrar cada línea parseada
   for(int i = 0; i < line_count && i < 15; i++) // Mostrar máximo 15 líneas
   {
      string line = lines[i];
      
      // Limpiar espacios
      while(StringLen(line) > 0 && StringGetCharacter(line, 0) == ' ')
         line = StringSubstr(line, 1);
      while(StringLen(line) > 0 && StringGetCharacter(line, StringLen(line)-1) == ' ')
         line = StringSubstr(line, 0, StringLen(line)-1);
      
      Print("Línea ", i, ": '", line, "' (", StringLen(line), " chars)");
      
      // Si no es la cabecera, parsear campos
      if(i > 0 && StringLen(line) > 3)
      {
         string fields[];
         int cnt = StringSplit(line, ';', fields);
         Print("  → Campos encontrados: ", cnt);
         if(cnt >= 5)
         {
            Print("    event_type: '", fields[0], "'");
            Print("    ticket: '", fields[1], "'");
            Print("    order_type: '", fields[2], "'");
            Print("    lots: '", fields[3], "'");
            Print("    symbol: '", fields[4], "'");
            if(cnt > 7)
               Print("    sl: '", fields[7], "'");
            if(cnt > 8)
               Print("    tp: '", fields[8], "'");
         }
      }
      Print("");
   }
   
   Print("========================================");
   Print("TEST completado");
   Print("========================================");
}

//+------------------------------------------------------------------+

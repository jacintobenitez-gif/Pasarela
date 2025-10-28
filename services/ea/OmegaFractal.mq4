//+------------------------------------------------------------------+
//|                                                OmegaFractal8.mq4 |
//|                                  Copyright 2025, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025, MetaQuotes Ltd."
#property link      "https://www.mql5.com"
#property strict

input ENUM_TIMEFRAMES PeriodoFractal = PERIOD_M30;
input ENUM_TIMEFRAMES PeriodoMACRO   = PERIOD_M15;
input ENUM_TIMEFRAMES PeriodoMESO    = PERIOD_M5;
input ENUM_TIMEFRAMES PeriodoMICRO   = PERIOD_M1;

input bool  PintarSeparadoresDia   = true;
input int   DiasSeparadoresHist    = 1;           // cuántos días hacia atrás
input color ColorSeparadorDia      = clrDimGray;
input int   EstiloSeparadorDia     = STYLE_DOT;
input int   AnchoSeparadorDia      = 3;
input bool  GoLive                 = true;

//ZigZag
double   ZZAux[];
datetime ZZAuxTime[];
double   ZZAuxFractal[];
int ZZAuxDirFractal[];

//Direcciones
int DIR_NODIR  = 0;
int DIR_LARGOS = 1;
int DIR_CORTOS = -1;
int FRACTAL_UP = 1;
int FRACTAL_DN = -1;
int FRACTAL_NODIRECTION = -1000;

//Variables Globales
int MV32_Depth = 32;
int MV8_Depth = 8;
int Deviation = 5;
int Backstep = 3;
string Par = Symbol();
int Digitos = (int)MarketInfo(Par, MODE_DIGITS);
bool NotificacionEnviada = false;
bool LecturaMercado = true;
bool EntradaMercado = false;
bool SalidaMercado = false;
bool PintadoPrecio = false;
bool PintadaEntrada = false;
double version = 8.00;

//Trazas
string Traza1 = "";
string Traza2 = "";
string Traza3 = "";
string Traza4 = "";
string Traza5 = "";
string Traza6 = "";
string Traza7 = "";
int Log = 1;

//Fractal
double FractalLeido  = 0;
double FractalActual = 0;
double FractalActualMACRO = 0;
double FractalActualMESO  = 0;
double StopLoss = 0;
int DireccionFractal = FRACTAL_NODIRECTION;

//Inversion
double capital   = 0;   
double inversion  = 0;                        
double valorLote  = 0; 
double lotespotencialesainvertir = 0; 
string commentSalida = "";  

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//---
   
//---
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
//---
   if(PintarSeparadoresDia)
      EnsureTodaySeparator();

   if (LecturaMercado)
   {
      FractalLeido = GetLastFractal(DireccionFractal);
      
      if (FractalLeido != FractalActual)
      {
         Trazas(" Fractal Leido: " + DoubleToStr(FractalLeido, Digitos) +  " Fractal Actual: " + DoubleToStr(FractalActual, Digitos) + " Direccion Fractal: " + IntegerToString(DireccionFractal), Traza1);
         FractalActual = FractalLeido;
         //Reset
         Reset();         
      }
      else if (FractalLeido == FractalActual)
      {
         Trazas(" Fractal Leido: " + DoubleToStr(FractalLeido, Digitos) +  " Fractal Actual: " + DoubleToStr(FractalActual, Digitos) + " Direccion Fractal: " + IntegerToString(DireccionFractal), Traza1);
         FractalActualMACRO = GetLastestFractalsInMACRO(PeriodoMACRO, FractalActual, DireccionFractal);            
         
         if (FractalActualMACRO > 0)
         {
            FractalActualMESO = GetLastFractalInMESO(PeriodoMESO, FractalActual, FractalActualMACRO, DireccionFractal);
            
            if (FractalActualMESO > 0)
            {
               if (GetLastestFractalInMICRO(PeriodoMICRO, FractalActual, FractalActualMESO, DireccionFractal))
               {
                  if (DireccionFractal == FRACTAL_DN)
                     if ((!GoLive) && (!PintadaEntrada))
                     {
                        string mensaje = Par + " Entrada: " + DoubleToStr(Ask);
                        PlotBigPointM1WithLabel(0, mensaje, clrGreen, clrBlack);
                        PintadaEntrada = true;
                        SendNotification(mensaje);
                     }
                     else if (GoLive)
                     {
                        LecturaMercado = false;
                        EntradaMercado = true;
                        SalidaMercado = false;
                     }
                  else if (DireccionFractal == FRACTAL_UP)
                  {
                     if ((!GoLive) && (!PintadaEntrada)) 
                     {
                        string mensaje = Par + " Entrada: " + DoubleToStr(Bid);
                        PlotBigPointM1WithLabel(1, mensaje, clrRed, clrBlack);
                        PintadaEntrada = true;
                        SendNotification(mensaje);
                     }
                     else if (GoLive)
                     {
                        LecturaMercado = false;
                        EntradaMercado = true;
                        SalidaMercado = false;
                     }
                  }
                  LotsForMarginPercent(0.7);
               }
            }
         }
      }
      
      Comment(Traza1, 
      "\n--------------------------------", 
      Traza2,
      "\n--------------------------------", 
      Traza3,
      "\n--------------------------------", 
      Traza4,
      "\n--------------------------------", 
      Traza5,
      "\n--------------------------------");
      
   }
   else if (EntradaMercado)
   { 
      Traza6 = "";
      Trazas("EntradaMercado", Traza6);
          
      if (!GoLive)
      {
         LecturaMercado = false;
         EntradaMercado = false;
         SalidaMercado  = true;            
      }
      else if (GoLive)
      { 
         commentSalida = Par + "-P1";
         Trazas("EntradaMercado--> CommentSalida:" + commentSalida, Traza6);
         
         int OperacionesAbiertas = ExecMarket(DireccionFractal, 1, StopLoss, lotespotencialesainvertir, commentSalida);
         Trazas("EntradaMercado--> Operaciones Abiertas: " + IntegerToString(OperacionesAbiertas), Traza6);

         //Ejecutas orden en el mercado
         if (OperacionesAbiertas > 0)
         {
            LecturaMercado = false;
            EntradaMercado = false;
            SalidaMercado  = true;
         }
         
         //Me falta meter un control de numero de reintentos. Si al X reintento
         //falla invalido la jugada.
         
      }
      
      Comment(Traza1, 
      "\n--------------------------------", 
      Traza2,
      "\n--------------------------------", 
      Traza3,
      "\n--------------------------------", 
      Traza4,
      "\n--------------------------------", 
      Traza5,
      "\n--------------------------------",
      Traza6);
         
   }
   else if (SalidaMercado)
   {
      Traza7 = "\nSalidaMercado";
      
      bool EstadoSalida = Salida(DireccionFractal);
      Trazas("\nEstado Salida: " + IntegerToString(EstadoSalida), Traza7);
      
      if (EstadoSalida)
      {
         if (!GoLive)
         {
            if (DireccionFractal == FRACTAL_DN)
            {
               PlotBigPointM1WithLabel(0, "Salida: " + DoubleToStr(Bid), clrBlack, clrBlack);            
            }
            else if (DireccionFractal == FRACTAL_UP)
            {
               PlotBigPointM1WithLabel(0, "Salida: " + DoubleToStr(Ask), clrBlack, clrBlack);                        
            }

            LecturaMercado = true;
            EntradaMercado = false;
            SalidaMercado  = false;  
            
         }
         else if (GoLive)
         {
            int cerradas = CierreOrdenes(commentSalida);

            Trazas("\nOrdenes Cerradas: " + IntegerToString(cerradas), Traza7);
            
            // Reset de estado si ya no quedan órdenes con ese comentario
            if (cerradas > 0)
            {
               LecturaMercado = true;
               EntradaMercado = false;
               SalidaMercado = false;               
            }         
         }         
      }
      
      Comment(Traza1, 
      "\n--------------------------------", 
      Traza2,
      "\n--------------------------------", 
      Traza3,
      "\n--------------------------------", 
      Traza4,
      "\n--------------------------------", 
      Traza5,
      "\n--------------------------------",
      Traza6, 
      "\n--------------------------------",
      Traza7);
   }
}
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//                      FUNCIONES BASICAS

void ZigZagFractal(string sMarket, ENUM_TIMEFRAMES iPeriodo, int ZZPeriodo, int iIteraciones)
{
   int    n = 0;
   int    i = 0;
   double zig = 0.0;
   bool   bSalida = false;

   if (iIteraciones < 1) iIteraciones = 1;

   ArrayResize(ZZAux,     iIteraciones);
   ArrayResize(ZZAuxTime, iIteraciones);
   ArrayResize(ZZAuxFractal, iIteraciones);
   ArrayResize(ZZAuxDirFractal, iIteraciones);
   ArrayInitialize(ZZAux,     0.0);
   ArrayInitialize(ZZAuxTime, 0);
   ArrayInitialize(ZZAuxFractal, 0);
   ArrayInitialize(ZZAuxDirFractal, 0);

   // Recorre desde la barra más reciente hacia atrás
   while ((n < iIteraciones) && (bSalida == false))
   {
      zig = iCustom(sMarket, iPeriodo, "ZigZag", ZZPeriodo, Deviation, Backstep, 0, i);
      
      if(zig > 0.0)
      {
         ZZAux[n]     = zig;                         // precio pivote
         ZZAuxTime[n] = iTime(sMarket, iPeriodo, i); // tiempo pivote
         
         double up  = iFractals(Par, iPeriodo, MODE_UPPER, i);
         double dn  = iFractals(Par, iPeriodo, MODE_LOWER, i);

         if ((up > 0) && (up == zig))
         {
            ZZAuxFractal[n] = up;
            ZZAuxDirFractal[n] = FRACTAL_UP;
         }

         if ((dn > 0) && (dn == zig))
         {
            ZZAuxFractal[n] = dn;
            ZZAuxDirFractal[n] = FRACTAL_DN;
         }
            
         if ((up == 0) && (dn == 0))
         {
            ZZAuxFractal[n] = 0;
            ZZAuxDirFractal[n] = FRACTAL_NODIRECTION;
         }
         
         n++;
      }
      
      i++;
      
      if (i > 2000) bSalida = true;
   }
}

double GetLastFractal(int &DirFractal)
{
   Traza1 = "";
   Traza1 = Traza1 + "V: " + DoubleToStr(version, 2) + " - GoLive: " + IntegerToString(GoLive);
   ZigZagFractal(Par, PeriodoFractal, MV8_Depth, 2);
   
   if (ZZAuxFractal[0] == ZZAux[0])
   {  
      if (ZZAux[0] > ZZAux[1])
      {
         //Largos 
         datetime f_TimeMICRO = 0;
         
         if (FindZigZagInMICRO(PeriodoFractal, ZZAux[0], ZZAuxTime[0], PeriodoMICRO, f_TimeMICRO))
         {
            DrawVLine(f_TimeMICRO, clrRed); 
         }
         
         DirFractal = ZZAuxDirFractal[0];
         Trazas(" Fractal activo UP (" + IntegerToString(PeriodoFractal)  + "): " + DoubleToStr(ZZAuxFractal[0])+  " Time: " +TimeToString(ZZAuxTime[0], TIME_DATE | TIME_SECONDS) + " Direccion Fractal: " + IntegerToString(DireccionFractal), Traza1);

         return(ZZAux[0]);
      }
      else if (ZZAux[0] < ZZAux[1])
      {
         //Cortos
         datetime f_TimeMICRO = 0;
         
         if (FindZigZagInMICRO(PeriodoFractal, ZZAux[0], ZZAuxTime[0], PeriodoMICRO, f_TimeMICRO))
         {
            DrawVLine(f_TimeMICRO, clrGreen); 
         }

         DirFractal = ZZAuxDirFractal[0];
         Trazas(" Fractal activo DN (" + IntegerToString(PeriodoFractal)  + "): " + DoubleToStr(ZZAuxFractal[0])+  " Time: " +TimeToString(ZZAuxTime[0], TIME_DATE | TIME_SECONDS) + " Direccion Fractal: " + IntegerToString(DireccionFractal), Traza1);

         return(ZZAux[0]);
      }
   } 
   else if (ZZAuxFractal[1] == ZZAux[1])
   {
      if (ZZAuxFractal[1] > ZZAuxFractal[0])
      {
         datetime f_TimeMICRO = 0;
         
         if (FindZigZagInMICRO(PeriodoFractal, ZZAuxFractal[1], ZZAuxTime[1], PeriodoMICRO, f_TimeMICRO))
         {
            DrawVLine(f_TimeMICRO, clrRed); 
         }      

         DirFractal = ZZAuxDirFractal[1];
         Trazas(" Fractal activo DN (" + IntegerToString(PeriodoFractal)  + "): " + DoubleToStr(ZZAuxFractal[1])+  " Time: " +TimeToString(ZZAuxTime[1], TIME_DATE | TIME_SECONDS) + " Direccion Fractal: " + IntegerToString(DireccionFractal), Traza1);

         return(ZZAuxFractal[1]);
      }
      else
      {
         datetime f_TimeMICRO = 0;
         
         if (FindZigZagInMICRO(PeriodoFractal, ZZAuxFractal[1], ZZAuxTime[1], PeriodoMICRO, f_TimeMICRO))
         {
            DrawVLine(f_TimeMICRO, clrGreen); 
         }            

         DirFractal = ZZAuxDirFractal[1];
         Trazas(" Fractal activo DN (" + IntegerToString(PeriodoFractal)  + "): " + DoubleToStr(ZZAuxFractal[1])+  " Time: " +TimeToString(ZZAuxTime[1], TIME_DATE | TIME_SECONDS) + " Direccion Fractal: " + IntegerToString(DireccionFractal), Traza1);

         return(ZZAuxFractal[1]);
      }      
   }
      
   return 0;
}

double GetLastestFractalsInMACRO(ENUM_TIMEFRAMES tf_MACRO, double PriceFractal, int DirFractal, int Maxlookback = 2)
{

   if (Log == 1) Traza2 = "";
   int contador = 0;
   double Fractal[];

   ArrayResize(Fractal, Maxlookback);
   ArrayInitialize(Fractal,     0.0);
   
   int tfconvertido = ConversorTF(tf_MACRO);

   if (Log == 1) Traza2 = Traza2 + "\nGetLastestFractalsInMACRO: (" + IntegerToString(tf_MACRO)  + "): Precio fractal: " + DoubleToStr(PriceFractal) + " Direccion Fractal: " + IntegerToString(DirFractal);
   int total = iBars(Par, tfconvertido);  
          
   for (int i = 0; i < total; i++)
   {
      double up  = iFractals(Par, tfconvertido, MODE_UPPER, i);
      double dn  = iFractals(Par, tfconvertido, MODE_LOWER, i);
      
      if ((up > 0) && (DirFractal == FRACTAL_UP))
      {
         Fractal[contador] = up;          
         if (Log == 1) Traza2 = Traza2 + "\nGetLastestFractalsInMACRO--> Fractal UP encontrado: " + DoubleToStr(up);
         contador++;         
      }
      else if ((dn > 0) && (DirFractal == FRACTAL_DN))
      {
         Fractal[contador] = dn; 
         if (Log == 1) Traza2 = Traza2 + "\nGetLastestFractalsInMACRO--> Fractal DN encontrado: " + DoubleToStr(dn);
         contador++;          
      }      
      
      if (contador >= Maxlookback)
         break;
      
   }
   
   if (contador == Maxlookback)
   {
      if (Fractal[1] == PriceFractal)
      {
         //Coincidencia
         if (Log == 1) Traza2 = Traza2 + "\nGetLastestFractalsInMACRO: 1 coincidencia. Precio Fractal: " + DoubleToStr(Fractal[1]) + " Precio MACRO: " + DoubleToStr(Fractal[0]);
         return Fractal[0];
      }
      else
      {
         //Coincidencia
         if (Log == 1) Traza2 = Traza2 + "\nGetLastestFractalsInMACRO: 0 coincidencia";  
         return 0;    
      }
   }
   
   return 0;
   
}

double GetLastFractalInMESO(ENUM_TIMEFRAMES tf_MESO, double PriceFractal, double PriceMacro, int DirFractal)
{

   if (Log == 1) Traza3 = "";   
   int tfconvertido = ConversorTF(tf_MESO);
   if (Log == 1) Traza3 = Traza3 + "\nGetLastFractalsInMESO: (" + IntegerToString(tfconvertido) + ") Precio Fractal: " + DoubleToStr(PriceFractal) + " Precio MACRO: " + DoubleToStr(PriceMacro) + " Direccion Fractal: " + IntegerToString(DirFractal);

   ZigZagFractal(Par, tf_MESO, MV8_Depth, 3);
   if(ZZAuxFractal[0] == 0.0 || ZZAuxFractal[1] == 0.0 || ZZAuxFractal[2] == 0.0) return 0;
   
   if (Log == 1) Trazas(" V0: " + DoubleToStr(ZZAuxFractal[0], Digitos) + " V1: " + DoubleToStr(ZZAuxFractal[1], Digitos) + " V2: " + DoubleToStr(ZZAuxFractal[2], Digitos), Traza3);

   if (DirFractal == FRACTAL_DN)
   {
      if ((ZZAuxFractal[2] == PriceFractal) && (ZZAuxFractal[0] < ZZAuxFractal[1]) && (ZZAuxFractal[0] > ZZAuxFractal[2]) 
      && (ZZAuxFractal[1] > ZZAuxFractal[2]) && (ZZAuxFractal[0] == PriceMacro))
      {
         if (Log == 1) Trazas(" ONDA 2 Largos (8)", Traza3);
         //ONDA 2 Largos
         return ZZAuxFractal[0];
      }
   }
   else if (DirFractal == FRACTAL_UP)
   {
      if ((ZZAuxFractal[2] == PriceFractal) && (ZZAuxFractal[0] > ZZAuxFractal[1]) && (ZZAuxFractal[0] < ZZAuxFractal[2]) 
      && (ZZAuxFractal[1] < ZZAuxFractal[2]) && (ZZAuxFractal[0] == PriceMacro))
      {
   
         if (Log == 1) Trazas(" ONDA 2 Cortos (8)", Traza3);
         //ONDA 2 Cortos
         return ZZAuxFractal[0];
      }
   }
   
   return 0;
   
}

bool GetLastestFractalInMICRO(ENUM_TIMEFRAMES tf_MICRO, double PriceFractal, double PriceMESO, int DirFractal)
{

   if (Log == 1) Traza4 = "";   
   int tfconvertido = ConversorTF(tf_MICRO);
   if (Log == 1) Traza4 = Traza4 + "\nGetLastestFractalInMICRO: (" + IntegerToString(tfconvertido) + ") Precio Fractal: " + DoubleToStr(PriceFractal) + " Precio MESO: " + DoubleToStr(PriceMESO) + " Direccion Fractal: " + IntegerToString(DirFractal);

   ZigZagFractal(Par, tf_MICRO, MV32_Depth, 4);
   if(ZZAuxFractal[0] == 0.0 || ZZAuxFractal[1] == 0.0 || ZZAuxFractal[2] == 0.0 || ZZAuxFractal[3] == 0.0) return false;
   
   if (Log == 1) Trazas(" R0: " + DoubleToStr(ZZAuxFractal[0], Digitos) + " R1: " + DoubleToStr(ZZAuxFractal[1], Digitos) + " R2: " + DoubleToStr(ZZAuxFractal[2], Digitos) + " R3: " + DoubleToStr(ZZAuxFractal[3], Digitos), Traza4);

   if (DirFractal == FRACTAL_DN) 
   {
      if ((ZZAuxFractal[2] == PriceFractal) && (ZZAuxFractal[0] < ZZAuxFractal[1]) && (ZZAuxFractal[0] > ZZAuxFractal[2]) 
      && (ZZAuxFractal[1] > ZZAuxFractal[2]) && (ZZAuxFractal[0] == PriceMESO))
      {
         if (Log == 1) Trazas(" ONDA 2 Largos (32)", Traza4);
         //ONDA 2 Largos
         return true;
      }

      if ((ZZAuxFractal[3] == PriceFractal) && (ZZAuxFractal[0] > ZZAuxFractal[1]) && (ZZAuxFractal[1] < ZZAuxFractal[2]) 
      && (ZZAuxFractal[1] > ZZAuxFractal[3])  && (ZZAuxFractal[2] > ZZAuxFractal[3]) && (ZZAuxFractal[1] == PriceMESO))
      {   
         if (Log == 1) Trazas(" ONDA 3 Largos (32)", Traza4);
         //ONDA 3 Largos
         return true;
      }
      
   }
   else if (DirFractal == FRACTAL_UP) 
   {
      if ((ZZAuxFractal[2] == PriceFractal) && (ZZAuxFractal[0] > ZZAuxFractal[1]) && (ZZAuxFractal[0] < ZZAuxFractal[2]) 
      && (ZZAuxFractal[1] < ZZAuxFractal[2]) && (ZZAuxFractal[0] == PriceMESO))
      {
   
         if (Log == 1) Trazas(" ONDA 2 Cortos (32)", Traza4);
         //ONDA 2 Cortos
         return true;
      }

      if ((ZZAuxFractal[3] == PriceFractal) && (ZZAuxFractal[0] < ZZAuxFractal[1]) && (ZZAuxFractal[1] > ZZAuxFractal[2]) 
      && (ZZAuxFractal[1] < ZZAuxFractal[3])  && (ZZAuxFractal[2] < ZZAuxFractal[3]) && (ZZAuxFractal[1] == PriceMESO))
      { 
         if (Log == 1) Trazas(" ONDA 3 Cortos (32)", Traza4);
         //ONDA 3 Cortos
         return true;
      }
   }

   
   return false;
   
}

bool Salida(int DirFractal)
{
   bool bSalida = false;

   if (Log == 1) Trazas("Salida: DireccionFractal:" + IntegerToString(DireccionFractal), Traza7);

   //Leyendo las ultima posición del periodo MICRO
   ZigZagFractal(Par, PeriodoMICRO, MV32_Depth, 2);   
   if(ZZAux[0] == 0.0 || ZZAux[0] == 0.0) return false;
   double ZZ0MICRO32 = ZZAux[0];
   double ZZ1MICRO32 = ZZAux[1];
   
   ZigZagFractal(Par, PeriodoMESO, MV8_Depth, 1);   
   if(ZZAux[0] == 0.0) return false;
   double ZZ0MESO8 = ZZAux[0];

   if (Log == 1) Trazas("ZZ0MICRO32:" + DoubleToStr(ZZ0MICRO32) + " ZZ1MICRO32:" + DoubleToStr(ZZ1MICRO32) + " ZZ0MESO8:" + DoubleToStr(ZZ0MESO8), Traza7);
   
   if (DirFractal == FRACTAL_DN) 
   {
      if (Log == 1) Trazas("Fractal DN", Traza7);

      if ((ZZ0MICRO32 > ZZ1MICRO32) && (ZZ0MICRO32 == ZZ0MESO8))
      {
         //ONDA 3
         if (Log == 1) Trazas("Salida ONDA 3 Largos", Traza7);
         Comment(Traza7, 
         "\n--------------------------------"); 
         bSalida = true;
      }  
   }
   else if (DirFractal == FRACTAL_UP) 
   {
      if (Log == 1) Trazas("Fractal UP", Traza7);

      if ((ZZ0MICRO32 < ZZ1MICRO32) && (ZZ0MICRO32 == ZZ0MESO8))
      {
         //ONDA 3
         if (Log == 1) Trazas("Salida ONDA 3 Cortos", Traza7);
         Comment(Traza7, 
         "\n--------------------------------");
         bSalida = true;
      }   
   }      
      
   if (Log == 1) Trazas("Resultado:" + IntegerToString(bSalida), Traza7);

   return(bSalida);
}

bool FindZigZagInMICRO(ENUM_TIMEFRAMES tfBase,
                        double priceTarget,
                        datetime tFractalTF,   // tiempo de la barra del Periodo 
                        ENUM_TIMEFRAMES tfMicro,
                        datetime &t_Micro)
{
   int     tfm    = ConversorTF(tfMicro);
   int     tfb    = ConversorTF(tfBase);
   datetime tBeg  = tFractalTF;                        // inicio barra 
   datetime tEnd  = tFractalTF + PeriodSeconds(tfb);   // fin barra 
   t_Micro = 0;
   
   // empezamos en la barra M1 más cercana a tEnd-1 (para incluir todo el tramo)
   int shift = iBarShift(Par, tfm, tEnd, true);
   if(shift < 0) return false;

   for(int s = shift; s < iBars(Par, tfm); s++)
   {
      datetime tt = iTime(Par, tfm, s);
      if(tt < tBeg) break;                // ya salimos por el principio de la ventana
      if(tt >= tEnd) continue;            // estamos por delante; retrocede

      double zz = iCustom(Par, tfm, "ZigZag", MV32_Depth, Deviation, Backstep, 0, s);
      // Verificamos igualdad por precio entre
      //Zigzag PeriodoMiCRO con el valor del Fractal del PeriodoFractal
            
      if ((zz != 0.0) && NormalizeDouble(zz, Digitos) == NormalizeDouble(priceTarget, Digitos))
      {
         t_Micro = tt;

         // Verificamos igualdad por precio entre
         //fractal del PeriodoMiCRO con el valor del Fractal del PeriodoMICRO.
         double fUp = iFractals(Par, tfm, MODE_UPPER, s);
         double fDn = iFractals(Par, tfm, MODE_LOWER, s);
         
         if ((NormalizeDouble(fUp, Digitos) == NormalizeDouble(priceTarget, Digitos)) 
         || (NormalizeDouble(fDn, Digitos) == NormalizeDouble(priceTarget, Digitos)))
         {
            return true;
         }         
      }
   }
   
   return false;
}



// Abre X órdenes de mercado por dirección.
// - dir: DIR_LARGOS o DIR_CORTOS
// - maxOps: máximo de órdenes abiertas permitidas para esa dirección (símbolo actual)
// - lots: tamaño de lote para cada orden nueva
// - sl: vendrá del exterior.
// - comment: comentario opcional de la orden.
// Devuelve numero de operaciones abiertas.
int ExecMarket(int dir, int maxOps, double sl = 0, double lots = 0.1, string comment = "")
{

   RefreshRates();

   int    slippage   = 3;      // puedes ajustar
   int    k          = 0;
   int    opened     = 0;
   double sl_price   = NormalizeDouble(sl, Digitos);
   
   for(k=0; k<maxOps; k++)
   {
      RefreshRates();
      double price = 0, tp = 0;
      int    type = 0;
      int magic = 31071974;

      if (dir == FRACTAL_DN)
      {
         type  = OP_BUY;
         price = NormalizeDouble(Ask, Digitos);
         tp    = 0.0;
      }
      else if (dir == FRACTAL_UP)
      {
         type  = OP_SELL;
         price = NormalizeDouble(Bid, Digitos);
         tp    = 0.0;
      }

      // Enviar orden
      int ticket = OrderSend(Par, type, lots, price, slippage, sl_price, tp, comment, magic, 0, clrNONE);
      if(ticket < 0)
      {
         // Si falla, intentamos seguir con el resto (por si es un fallo puntual)
         // Puedes loguear el error:
         Print("OrderSend error: ", GetLastError());
      }
      else
         opened++;
   }

   return (opened);
}

int CierreOrdenes(string targetComment)
{
   RefreshRates();
   int contador = 0;

   if (Log == 1) Trazas("\nCierreOrdenes: TargetComment: " + targetComment, Traza7);

   for(int i = OrdersTotal()-1; i >= 0; i--)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
      {
         // Comparación EXACTA (sensible a mayúsculas/minúsculas)
         if (Log == 1) Trazas("\nOrderComment: " + OrderComment(), Traza7);

         if(OrderComment() == targetComment)
         {
            int ticket = OrderTicket();
            int type   = OrderType();
            RefreshRates();
            double price = (type==OP_BUY) ? Bid : Ask;
            bool ok = OrderClose(ticket, OrderLots(), NormalizeDouble(price, Digitos), 3);
            if (ok)
               contador++;   
            else
               if (Log == 1) Trazas("\nOrderClose error ticket=" + IntegerToString(ticket) +  " Error code=" + IntegerToString(GetLastError()), Traza7); 
         }
      }
   }

   if (Log == 1) Trazas("\nCierreOrdenes: Ordenes cerradas: " + IntegerToString(contador), Traza7);  

   Comment(Traza7, 
   "\n--------------------------------");
    
   return(contador);   
}

double LotsForMarginPercent(double percent, bool useEquity=true)
{
   if (Log == 1) Traza5 = "";
   if (Log == 1) Traza5 = Traza5 + "\nLotsForMarginPercent: " + DoubleToStr(percent, Digitos);    
   capital   = useEquity ? AccountEquity() : AccountBalance();   
   inversion  = capital * percent;                        // p.ej., 0.70
   valorLote  = MarketInfo(Par, MODE_MARGINREQUIRED);   // margen por 1.00 lot
   if(valorLote <= 0.0) return 0.0;
   double lotsRaw = inversion / valorLote;

   // Ajuste a los límites/step del símbolo
   double minL = MarketInfo(Par, MODE_MINLOT);
   double maxL = MarketInfo(Par, MODE_MAXLOT);
   double step = MarketInfo(Par, MODE_LOTSTEP);
   lotespotencialesainvertir = MathFloor(lotsRaw/step) * step;   
   
   if (Log == 1) Traza5 = Traza5 + "\nLotsForMarginPercent: Capital: " + DoubleToStr(capital, Digitos) + " Inversion: " + DoubleToStr(inversion, Digitos);
   if (Log == 1) Traza5 = Traza5 + " Valor Lote: " + DoubleToStr(valorLote, Digitos) + " Lotes a Invertir: " + DoubleToStr(lotespotencialesainvertir, Digitos);

   // redondeo por debajo
   return MathMin(MathMax(lotespotencialesainvertir, minL), maxL);
}


//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//                      FUNCIONES AUXILIARES

//--------------------------------------------------------------
//--------------------------------------------------------------
// Punto gordo en Ask/Bid + texto superpuesto
// - side: 0 = ASK, 1 = BID
// - label: texto a mostrar sobre el punto
// - dotColor: color del punto
// - textColor: color del texto (usa contraste: ej. clrWhite)
// - dotWidth: grosor del punto (6-8 = muy gordo)
// - fontSize: tamaño de fuente del texto (12-16 típico)
//--------------------------------------------------------------
void PlotBigPointM1WithLabel(
   int    side       = 0,
   string label      = "",
   color  dotColor   = clrDodgerBlue,
   color  textColor  = clrWhite,
   int    dotWidth   = 7,
   int    fontSize   = 14
)
{
   double   price = (side == 0 ? Ask : Bid);
   price = NormalizeDouble(price, Digits);

   datetime tnow = TimeCurrent(); // instante actual (vela M1 en curso)

   // Nombres únicos
   string base = StringFormat("BigDotLbl_%s_%d_%u", Symbol(), (int)tnow, GetTickCount());
   string nameDot  = base + "_DOT";
   string nameText = base + "_TXT";

   // 1) Punto sólido (● Wingdings 159)
   if(!ObjectCreate(0, nameDot, OBJ_ARROW, 0, tnow, price))
   {
      Print("ObjectCreate DOT falló: ", GetLastError());
      return;
   }
   ObjectSetInteger(0, nameDot, OBJPROP_ARROWCODE, 159);
   ObjectSetInteger(0, nameDot, OBJPROP_COLOR,     dotColor);
   ObjectSetInteger(0, nameDot, OBJPROP_WIDTH,     dotWidth);
   ObjectSetInteger(0, nameDot, OBJPROP_BACK,      false);
   ObjectSetInteger(0, nameDot, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, nameDot, OBJPROP_HIDDEN,    false);
   ObjectSetInteger(0, nameDot, OBJPROP_READONLY,  true);

   // 2) Texto superpuesto en el mismo (t, price)
   if(!ObjectCreate(0, nameText, OBJ_TEXT, 0, tnow, price))
   {
      Print("ObjectCreate TXT falló: ", GetLastError());
      return;
   }
   // Centrado y encima (si tu build soporta ANCHOR_CENTER, lo usamos)
   ObjectSetInteger(0, nameText, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetInteger(0, nameText, OBJPROP_BACK,   false);
   ObjectSetInteger(0, nameText, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nameText, OBJPROP_HIDDEN, false);
   ObjectSetInteger(0, nameText, OBJPROP_READONLY, true);

   // Texto (fuente estándar legible)
   ObjectSetText(nameText, label, fontSize, "Arial", textColor);

   // Nota: si el texto se ve ligeramente descentrado por el zoom,
   // puedes aplicar un micro-desplazamiento en precio:
   // double pip = (Digits==3 || Digits==5) ? 10*Point : Point;
   // ObjectMove(0, nameText, 0, tnow, price + 0.0*pip); // ajusta 0.0→±pips
}


ENUM_TIMEFRAMES GetCurrentPeriod()
{
   return (ENUM_TIMEFRAMES)Period();
}

void Reset()
{
   NotificacionEnviada = false;
   PintadoPrecio = false; 
   PintadaEntrada = false;  
   StopLoss = 0;
   commentSalida = ""; 
   Traza2 = "";
   Traza3 = "";
   Traza4 = "";
   Traza5 = "";
   Traza6 = "";
     
}

void Trazas(string cadena, string &Textofinal)
{
   string cadenafinal = "\n" + NowHMSStr() + cadena;
   Textofinal = Textofinal + cadenafinal;
}

string NowHMSStr()
{
   return TimeToString(TimeCurrent(), TIME_SECONDS); // "YYYY.MM.DD HH:MM:SS"
}


void DrawVLine(datetime t_m1, color c=clrDodgerBlue)
{
   string name = StringFormat("Fractal_%s_%s", Par, TimeToString(t_m1, TIME_DATE|TIME_MINUTES|TIME_SECONDS));
   
   if(ObjectFind(0, name) >= 0) return;
   
   ObjectCreate(0, name, OBJ_VLINE, 0, t_m1, 0);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   
}


int ConversorTF(ENUM_TIMEFRAMES tf)
{
   int tfconvertido = 0;
   
   if (tf == PERIOD_M1)
      tfconvertido = PERIOD_M1;
   else if (tf == PERIOD_M5)
      tfconvertido = PERIOD_M5;
   else if (tf == PERIOD_M15)
      tfconvertido = PERIOD_M15;
   else if (tf == PERIOD_M30)
      tfconvertido = PERIOD_M30;
   else if (tf == PERIOD_H1)
      tfconvertido = PERIOD_H1;
   else if (tf == PERIOD_H4)
      tfconvertido = PERIOD_H4;
   
   return(tfconvertido);
   
}

// Pinta N días hacia atrás usando las velas D1
void DrawDailySeparators(int days_back)
{
   if(!PintarSeparadoresDia) return;

   for(int i=0; i<days_back; i++)
   {
      datetime dOpen = iTime(Par, PERIOD_D1, i);
      if(dOpen <= 0) break;
      DrawDaySeparator(dOpen);
   }
}

// Asegura que el separador del día (hoy) existe
void EnsureTodaySeparator()
{
   if(!PintarSeparadoresDia) return;

   datetime todayOpen = iTime(Par, PERIOD_D1, 0);
   if(todayOpen > 0)
      DrawDaySeparator(todayOpen);
}

void DrawDaySeparator(datetime dayOpen)
{
   string name = StringFormat("DaySep_%s_%s", Par, TimeToString(dayOpen, TIME_DATE));
   if(ObjectFind(0, name) >= 0) return;

   ObjectCreate(0, name, OBJ_VLINE, 0, dayOpen, 0);
   ObjectSetInteger(0, name, OBJPROP_COLOR, ColorSeparadorDia);
   ObjectSetInteger(0, name, OBJPROP_STYLE, EstiloSeparadorDia);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, AnchoSeparadorDia);
}
